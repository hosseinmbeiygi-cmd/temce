"""
BrsApi Budget Governor
======================

A supervisor that prevents the BrsApi key from getting blocked AGAIN.

The in-process :class:`~brsapi.rate_limiter.RateLimiter` enforces the daily
and 5-minute caps, but its counters live in memory only. In a multi-replica
Swarm or after a restart every process starts with a fresh budget — which is
exactly how the account exceeded the real plan cap (~5,000/day), hit 19k and
got blocked.

``BrsApiBudgetGovernor`` closes that gap by making the global counters
PERSISTENT and SHARED across processes/restarts:

  1. **Daily counter** — Redis ``INCRBY`` (atomic across processes) keyed by
     the Tehran calendar date, TTL until Tehran midnight + slack. Falls back
     to a JSON file (``json/brsapi/budget_state.json``), then to memory.
  2. **5-min window** — Redis sorted set of request timestamps (pruned
     sliding window) shared by every process. Falls back to the in-process
     limiter window.
  3. **Block state** — an HTTP 302 heavy-file redirect (the server's "you are
     over quota" signal) arms a cooldown during which EVERY live call is
     rejected fast; the block clears only after the cooldown elapses AND the
     server answers HTTP 200.

It layers on top of the existing ``RateLimiter`` (which keeps the per-category
token buckets + threshold notifications) and seeds the limiter's in-memory
daily count from persistence so a restarted process does NOT get a fresh
budget.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from logging import getLogger
from pathlib import Path
from typing import Any

logger = getLogger(__name__)

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))
FIVE_MINUTES_SECONDS = 300

# Keep the daily key alive ~1h past Tehran midnight (safety slack).
_DAY_TTL_SLACK = 3600
# The 5-min sorted set never needs to live longer than one window.
_5MIN_TTL = 600
# Upper bound for a single Redis connect attempt during lazy init.
_REDIS_CONNECT_TIMEOUT = 2.0
# After a failed connect, do not retry Redis for a while (avoids a 2s stall
# on EVERY new client instance when Redis is down — e.g. in unit tests).
_REDIS_RETRY_INTERVAL = 60.0

# Redis-side check-and-reserve.  A plain INCRBY followed by a Python check
# consumes quota even when the request is rejected at the limit boundary.
_RESERVE_DAILY_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local requested = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
if current + requested > limit then
    return -1
end
local new_value = redis.call('INCRBY', KEYS[1], requested)
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
return new_value
"""

_LAST_REDIS_ATTEMPT_AT = 0.0

# Default state file lives next to the other brsapi runtime files.
DEFAULT_STATE_FILE = Path(__file__).resolve().parent.parent / "json" / "brsapi" / "budget_state.json"


class BudgetBlockedError(Exception):
    """Raised when the key is in the post-302 cooldown — reject the request fast.

    Failing fast here (instead of issuing the HTTP call) is what stops a job
    cascade from hammering an account the server already flagged as over
    quota.
    """


@dataclass
class _BlockState:
    """Server-side block signal (302 heavy-file redirect) state."""

    blocked_until: float = 0.0          # epoch seconds; 0 = not blocked
    last_302_at: float = 0.0            # epoch seconds
    last_302_location: str = ""
    count: int = 0                      # 302s observed since last clear


class BrsApiBudgetGovernor:
    """Persistent, cross-process budget governor for the BrsApi key.

    Usage::

        from brsapi.budget import get_budget_governor

        governor = get_budget_governor()
        await governor.acquire("tsetmc", endpoint="/Tsetmc/Symbol.php")

    The governor is also wired into :class:`brsapi.client.BrsApiClient`
    automatically — ``fetch()`` pre-checks the budget/block state and the
    client reports HTTP 302/200 results back so the cooldown stays current.
    """

    def __init__(
        self,
        rate_limiter: Any | None = None,
        daily_limit: int | None = None,
        five_min_limit: int | None = None,
        redis_client: Any | None = None,
        state_file: str | Path | None = None,
        block_cooldown: float | None = None,
        redis_prefix: str | None = None,
        fail_fast: bool | None = None,
        persist: bool = True,
        usage_recorder: Any | None = None,
    ) -> None:
        from brsapi.config import settings as brsapi_settings
        from brsapi.rate_limiter import get_rate_limiter

        self._limiter = rate_limiter or get_rate_limiter()
        self._usage_recorder = usage_recorder  # optional reporting sink
        self._daily_limit = daily_limit if daily_limit is not None else self._limiter._daily_limit
        self._five_min_limit = (
            five_min_limit if five_min_limit is not None else self._limiter._five_min_limit
        )
        self._fail_fast = (
            self._limiter._fail_fast if fail_fast is None else fail_fast
        )

        self._persist = persist
        self._redis: Any = redis_client
        self._redis_prefix = redis_prefix or brsapi_settings.budget_redis_prefix
        self._block_cooldown = (
            block_cooldown if block_cooldown is not None
            else float(brsapi_settings.budget_block_cooldown_seconds)
        )
        self._state_file = Path(state_file or brsapi_settings.budget_state_file or DEFAULT_STATE_FILE)

        self._lock = asyncio.Lock()
        self._initialized = False
        self._init_error: str | None = None
        self._backend = "none"  # "redis" | "file" | "memory"

        # In-memory fallbacks / mirrors
        self._block = _BlockState()

    # ── Tehran time helpers ──────────────────────────────

    @staticmethod
    def _tehran_today() -> str:
        return datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")

    @staticmethod
    def _seconds_to_midnight() -> float:
        now = datetime.now(TEHRAN_TZ)
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (midnight - now).total_seconds()

    # ── Initialization ───────────────────────────────────

    async def initialize(self) -> None:
        """Connect the persistence backend and seed local counters.

        Safe to call repeatedly (idempotent). Called lazily by every public
        method, so constructing the governor does no I/O.
        """
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            try:
                if self._persist:
                    if self._redis is None:
                        self._redis = await self._connect_redis()
                    if self._redis is not None:
                        self._backend = "redis"
                        await self._load_block_redis()
                    else:
                        self._backend = "file" if self._try_load_file() else "memory"
                else:
                    self._backend = "memory"
            except Exception as exc:  # noqa: BLE001
                self._init_error = str(exc)
                self._backend = "memory"
                logger.warning("BrsApi budget governor init failed (%s) — memory only", exc)
            await self._seed_limiter_from_persisted()
            self._initialized = True

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize()

    async def _connect_redis(self) -> Any | None:
        global _LAST_REDIS_ATTEMPT_AT
        now = time.time()
        if now - _LAST_REDIS_ATTEMPT_AT < _REDIS_RETRY_INTERVAL:
            return None
        # Reuse the app-wide cache client when it is already connected.
        try:
            from core.cache import get_cache

            cache = get_cache()
            if cache.is_connected and cache.client is not None:
                return cache.client
        except Exception:  # noqa: BLE001
            pass
        try:
            import redis.asyncio as aioredis

            from core.config import settings as core_settings

            client = aioredis.from_url(core_settings.redis_url, decode_responses=True)
            await asyncio.wait_for(client.ping(), timeout=_REDIS_CONNECT_TIMEOUT)
            return client
        except Exception as exc:  # noqa: BLE001
            _LAST_REDIS_ATTEMPT_AT = time.time()
            logger.debug("BrsApi budget governor: Redis unavailable (%s)", exc)
            return None

    async def _seed_limiter_from_persisted(self) -> None:
        """Keep the in-memory limiter in sync so a restarted process does not
        get a fresh budget. Only ever moves the count UP.

        Reads the persisted count from the ACTIVE backend (Redis key or the
        file mirror) so the limiter's threshold notifications (80/90/95/100%)
        and its local fail-fast gate reflect the GLOBAL usage, not just this
        process's.
        """
        if self._backend == "memory":
            return
        today = self._tehran_today()
        if self._limiter._daily_date == today:
            return
        persisted = self._persisted_daily_sync()
        if self._backend == "redis" and self._redis is not None:
            try:
                val = await self._redis.get(f"{self._redis_prefix}:daily:{today}")
                if val is not None:
                    persisted = int(val)
            except Exception:  # noqa: BLE001
                pass
        self._limiter._daily_count = max(self._limiter._daily_count, persisted)
        self._limiter._daily_date = today

    def _persisted_daily_sync(self) -> int:
        """Local (non-Redis) persisted daily count — file mirror, else 0."""
        return int(getattr(self, "_file_daily_count", 0) or 0)

    # ── File fallback ────────────────────────────────────

    def _try_load_file(self) -> bool:
        try:
            if not self._state_file.exists():
                self._file_daily_count = 0
                return True  # will be created on the first record
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
            today = self._tehran_today()
            self._file_daily_count = (
                int(raw.get("count", 0) or 0) if raw.get("date") == today else 0
            )
            b = raw.get("block") or {}
            self._block = _BlockState(
                blocked_until=float(b.get("blocked_until", 0) or 0),
                last_302_at=float(b.get("last_302_at", 0) or 0),
                last_302_location=str(b.get("last_302_location", "")),
                count=int(b.get("count", 0) or 0),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("BrsApi budget governor: state file load failed (%s)", exc)
            return False

    def _persist_file(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "date": self._tehran_today(),
                "count": int(self._limiter._daily_count or 0),
                "block": {
                    "blocked_until": self._block.blocked_until,
                    "last_302_at": self._block.last_302_at,
                    "last_302_location": self._block.last_302_location,
                    "count": self._block.count,
                },
            }
            tmp = self._state_file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._state_file)
            self._file_daily_count = int(self._limiter._daily_count or 0)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "BrsApi budget governor: state file write failed (%s) — memory only",
                exc,
            )
            self._backend = "memory"

    # ── Block state (302 heavy-file redirect) ────────────

    def _is_blocked_now(self) -> bool:
        return time.time() < self._block.blocked_until

    def _block_message(self) -> str:
        remain = max(0.0, self._block.blocked_until - time.time())
        loc = self._block.last_302_location or "heavy-file redirect"
        return (
            f"BrsApi key in 302-cooldown ({remain:.0f}s left, last redirect to {loc!r}) — "
            "server-side usage is above the plan threshold; requests rejected to "
            "protect the key"
        )

    async def _load_block_redis(self) -> None:
        if self._redis is None:
            return
        try:
            raw = await self._redis.get(f"{self._redis_prefix}:block")
            if raw:
                b = json.loads(raw)
                self._block = _BlockState(
                    blocked_until=float(b.get("blocked_until", 0) or 0),
                    last_302_at=float(b.get("last_302_at", 0) or 0),
                    last_302_location=str(b.get("last_302_location", "")),
                    count=int(b.get("count", 0) or 0),
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("BrsApi budget governor: block load failed (%s)", exc)

    async def _persist_block(self) -> None:
        if self._backend == "redis" and self._redis is not None:
            try:
                key = f"{self._redis_prefix}:block"
                payload = json.dumps(
                    {
                        "blocked_until": self._block.blocked_until,
                        "last_302_at": self._block.last_302_at,
                        "last_302_location": self._block.last_302_location,
                        "count": self._block.count,
                    }
                )
                await self._redis.set(key, payload)
                await self._redis.expire(key, int(self._block_cooldown) + 60)
            except Exception as exc:  # noqa: BLE001
                logger.debug("BrsApi budget governor: block persist failed (%s)", exc)
        elif self._backend == "file":
            self._persist_file()

    # ── Public API ───────────────────────────────────────

    async def check_allowed(
        self,
        category: str = "",
        endpoint: str = "",
        tokens: int = 1,
        fail_fast: bool | None = None,
    ) -> None:
        """Fail-fast pre-check before any live HTTP call.

        Raises :class:`BudgetBlockedError` when the key is in the 302 cooldown,
        or :class:`~brsapi.rate_limiter.RateLimitExhaustedError` when the
        (persisted) daily budget is gone. Passes when budget remains.
        """
        if fail_fast is None:
            fail_fast = self._fail_fast
        await self._ensure_initialized()

        if self._is_blocked_now():
            raise BudgetBlockedError(self._block_message())

        if not fail_fast:
            return

        used = await self._daily_used()
        if used >= self._daily_limit:
            raise self._exhausted_error(used)

        # Fast local gate via the in-process limiter (keeps the pre-existing
        # behaviour for callers that build a custom limiter).
        local = self._limiter.status()["global"]
        if local["daily_remaining"] <= 0:
            raise self._exhausted_error(local["daily_count"])

    def _exhausted_error(self, used: int) -> Exception:
        from brsapi.rate_limiter import RateLimitExhaustedError

        return RateLimitExhaustedError(
            f"BrsApi daily budget exhausted ({used}/{self._daily_limit}) — "
            "request rejected to protect the key"
        )

    async def acquire(
        self,
        category: str,
        tokens: int = 1,
        endpoint: str = "",
        fail_fast: bool | None = None,
    ) -> None:
        """Acquire permission for one live request.

        Enforces, in order: block cooldown → persisted daily cap → shared
        5-min window (Redis) → the in-process limiter (buckets + local caps).
        Usage is persisted only after the limiter grants the slot.
        """
        if fail_fast is None:
            fail_fast = self._fail_fast
        await self._ensure_initialized()

        if self._is_blocked_now():
            raise BudgetBlockedError(self._block_message())

        reserved_daily = False
        if fail_fast:
            if self._backend == "redis":
                # Reserve atomically in Redis.  The Lua path does not mutate
                # the counter when the request would exceed the cap.
                used = await self._reserve_daily(tokens)
                if used is None or used > self._daily_limit:
                    # ``used > limit`` is the compatibility fallback for
                    # clients without Redis EVAL; the Lua path returns None
                    # and leaves the counter untouched.
                    prior_used = await self._daily_used()
                    raise self._exhausted_error(
                        max(0, prior_used if used is None else used - tokens)
                    )
                reserved_daily = True
            else:
                used = await self._daily_used()
                if used >= self._daily_limit:
                    raise self._exhausted_error(used)

        try:
            await self._enforce_5min(fail_fast=fail_fast)
            await self._limiter.acquire(
                category,
                tokens=tokens,
                endpoint=endpoint,
                fail_fast=fail_fast,
            )
        except BaseException:
            # A reservation is not a granted request.  Release it when a
            # later local/window gate rejects or the coroutine is cancelled.
            if reserved_daily:
                await self._release_daily(tokens)
            raise

        await self._record_used(tokens)

    async def _reserve_daily(self, tokens: int) -> int | None:
        """Reserve ``tokens`` without consuming quota for a rejected request.

        Redis deployments use an atomic Lua check-and-set.  Lightweight test
        doubles and older Redis-compatible clients that do not expose ``eval``
        retain the conservative INCRBY fallback; that fallback is still
        race-safe, but may count a boundary rejection.
        """
        today = self._tehran_today()
        daily_key = f"{self._redis_prefix}:daily:{today}"
        ttl = int(self._seconds_to_midnight()) + _DAY_TTL_SLACK
        try:
            if hasattr(self._redis, "eval"):
                val = await self._redis.eval(
                    _RESERVE_DAILY_LUA,
                    1,
                    daily_key,
                    str(tokens),
                    str(self._daily_limit),
                    str(ttl),
                )
                value = int(val)
                return None if value < 0 else value

            # Compatibility fallback for minimal Redis clients.
            val = await self._redis.incrby(daily_key, tokens)
            await self._redis.expire(daily_key, ttl)
            return int(val)
        except Exception as exc:  # noqa: BLE001
            logger.debug("BrsApi budget governor: daily reserve failed (%s)", exc)
            # Degrade to the read-only check; the local limiter still enforces.
            return await self._daily_used()

    async def _release_daily(self, tokens: int) -> None:
        """Undo a reservation when a later gate rejects the request."""
        if self._backend != "redis" or self._redis is None or tokens <= 0:
            return
        try:
            key = f"{self._redis_prefix}:daily:{self._tehran_today()}"
            remaining = int(await self._redis.decrby(key, tokens))
            if remaining <= 0:
                await self._redis.delete(key)
        except Exception as exc:  # noqa: BLE001
            # Failing closed is safer than retrying a request, but the quota
            # may remain conservatively over-counted until Tehran midnight.
            logger.warning("Could not release BrsApi daily reservation: %s", exc)

    async def _enforce_5min(self, fail_fast: bool) -> None:
        """Shared sliding 5-min window (Redis backend only)."""
        from brsapi.rate_limiter import RateLimitExhaustedError

        if self._backend != "redis" or self._redis is None:
            return  # the in-process limiter enforces its own window
        key = f"{self._redis_prefix}:5min"
        try:
            while True:
                now = time.time()
                await self._redis.zremrangebyscore(key, 0, now - FIVE_MINUTES_SECONDS)
                count = int(await self._redis.zcard(key) or 0)
                if count < self._five_min_limit:
                    return
                if fail_fast:
                    raise RateLimitExhaustedError(
                        f"BrsApi 5-min window full ({count}/{self._five_min_limit}) — "
                        "request rejected to protect the key"
                    )
                oldest = await self._redis.zrange(key, 0, 0, withscores=True)
                wait = (float(oldest[0][1]) + FIVE_MINUTES_SECONDS - now) if oldest else 1.0
                await asyncio.sleep(min(max(wait, 0.1), 10.0))
        except RateLimitExhaustedError:
            raise  # never swallow the fail-fast rejection
        except Exception as exc:  # noqa: BLE001
            logger.debug("BrsApi budget governor: 5-min check failed (%s)", exc)

    async def _record_used(self, tokens: int = 1) -> None:
        if self._backend == "redis" and self._redis is not None:
            # NOTE: the daily counter was already reserved atomically in
            # ``acquire()`` — only the shared 5-min window is recorded here.
            try:
                now = time.time()
                five_key = f"{self._redis_prefix}:5min"
                member = f"{now:.6f}:{uuid.uuid4().hex[:8]}"
                await self._redis.zadd(five_key, {member: now})
                await self._redis.zremrangebyscore(five_key, 0, now - FIVE_MINUTES_SECONDS)
                await self._redis.expire(five_key, _5MIN_TTL)
            except Exception as exc:  # noqa: BLE001
                logger.debug("BrsApi budget governor: redis record failed (%s)", exc)
        elif self._backend == "file":
            self._persist_file()
        # memory backend: the in-process limiter already counted it

        # Reporting sink — never let it break the request path.
        if self._usage_recorder is not None:
            try:
                self._usage_recorder.record_used(tokens)
            except Exception as exc:  # noqa: BLE001
                logger.debug("BrsApi budget governor: usage recorder failed (%s)", exc)

    async def _daily_used(self) -> int:
        if self._backend == "redis" and self._redis is not None:
            try:
                val = await self._redis.get(f"{self._redis_prefix}:daily:{self._tehran_today()}")
                return int(val) if val is not None else 0
            except Exception:  # noqa: BLE001
                return 0
        return int(self._limiter._daily_count or 0)

    async def report_302(self, location: str = "") -> None:
        """Record an HTTP 302 heavy-file redirect (server over-quota signal).

        Arms the cooldown: every live call is rejected fast until the cooldown
        elapses AND the server answers 200 again.
        """
        await self._ensure_initialized()
        now = time.time()
        self._block.blocked_until = now + self._block_cooldown
        self._block.last_302_at = now
        self._block.last_302_location = location
        self._block.count += 1
        await self._persist_block()
        if self._usage_recorder is not None:
            try:
                self._usage_recorder.record_block(location)
            except Exception as exc:  # noqa: BLE001
                logger.debug("BrsApi budget governor: usage recorder block failed (%s)", exc)
        logger.warning(
            "BrsApi 302 detected (redirect to %r) — budget governor rejects live "
            "calls for %.0fs to protect the key",
            location,
            self._block_cooldown,
        )

    async def report_ok(self) -> None:
        """Record an HTTP 200. Clears the block once the cooldown has elapsed."""
        await self._ensure_initialized()
        if not self._is_blocked_now() and self._block.count > 0:
            # Cooldown elapsed (or never armed) and the server answered 200 →
            # the key is usable again; reset the block record.
            self._block = _BlockState()
            await self._persist_block()
            logger.info("BrsApi budget governor: block cleared (HTTP 200 after cooldown)")

    async def is_blocked(self) -> bool:
        await self._ensure_initialized()
        return self._is_blocked_now()

    async def available_daily(self) -> int:
        """Persisted daily budget still available for today."""
        await self._ensure_initialized()
        return max(0, self._daily_limit - await self._daily_used())

    async def stats(self) -> dict[str, Any]:
        """Full monitoring snapshot of the governor."""
        await self._ensure_initialized()
        used = await self._daily_used()
        blocked = self._is_blocked_now()

        if self._backend == "redis" and self._redis is not None:
            try:
                window = int(await self._redis.zcard(f"{self._redis_prefix}:5min") or 0)
            except Exception:  # noqa: BLE001
                window = len(self._limiter._5min_window)
        else:
            window = len(self._limiter._5min_window)

        def _iso(ts: float) -> str | None:
            return datetime.fromtimestamp(ts, tz=TEHRAN_TZ).isoformat() if ts else None

        return {
            "governor": {
                "backend": self._backend,
                "initialized": self._initialized,
                "init_error": self._init_error,
            },
            "global": {
                "daily_count": used,
                "daily_limit": self._daily_limit,
                "daily_remaining": max(0, self._daily_limit - used),
                "daily_used_pct": round(used / self._daily_limit * 100, 1) if self._daily_limit else 0.0,
                "daily_date": self._tehran_today(),
                "5min_count": window,
                "5min_limit": self._five_min_limit,
            },
            "block": {
                "blocked": blocked,
                "blocked_until": _iso(self._block.blocked_until) if blocked else None,
                "last_302_at": _iso(self._block.last_302_at),
                "last_302_location": self._block.last_302_location,
                "302_count": self._block.count,
                "cooldown_seconds": self._block_cooldown,
            },
            "limiter": self._limiter.status(),
        }


# ── Global singleton ─────────────────────────────────

_governor: BrsApiBudgetGovernor | None = None


def get_budget_governor() -> BrsApiBudgetGovernor:
    """Return the process-wide budget governor (persistent backend).

    The shared usage recorder is attached so granted requests and 302 blocks
    feed the ``brsapi_daily_usage`` report table (admin panel).
    """
    global _governor
    if _governor is None:
        _governor = BrsApiBudgetGovernor()
        try:
            from brsapi.usage_recorder import get_usage_recorder

            _governor._usage_recorder = get_usage_recorder()
        except Exception as exc:  # noqa: BLE001
            logger.debug("BrsApi budget governor: usage recorder attach failed (%s)", exc)
    return _governor
