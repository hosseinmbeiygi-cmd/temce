"""
Centralized rate limiter for ALL BrsApi.ir API calls.

Three layers enforced for EVERY request:
  1. Global daily limit   — max 4,000 requests/calendar day (Tehran time).
                            Default is kept BELOW the real plan cap (~5,000/day)
                            so the limiter never lets the key get blocked.
  2. Global 5-min window  — max 1,000 requests in any sliding 5-minute window
                            (upgraded plan limit)
  3. Per-category bucket  — token-bucket per endpoint category

Notification: fires a callback when daily usage hits 80%, 90%, 95%, 100%.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any

logger = getLogger(__name__)

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))


class RateLimitExhaustedError(Exception):
    """Raised by ``acquire(fail_fast=True)`` when a global quota is exhausted.

    Lets callers reject the request immediately instead of sleeping until the
    window/Tehran-midnight resets (the pre-fail-fast behaviour that caused
    blocked-key cascades when multiple jobs piled up past the quota).
    """

# ── Default global limits (overridable via BrsApiSettings) ──
# 4,000/day default keeps a safety margin below the real-world plan cap
# (~5,000/day, above which the key gets blocked). Override in .env with
# BRSAPI_GLOBAL_DAILY_LIMIT to match the exact purchased quota.
DEFAULT_GLOBAL_DAILY_LIMIT = 4_000
DEFAULT_GLOBAL_5MIN_LIMIT = 1_000
FIVE_MINUTES_SECONDS = 300

# Notification thresholds (percentage of daily limit)
NOTIFY_THRESHOLDS = [80, 90, 95, 100]


@dataclass
class Bucket:
    """Token bucket for a single endpoint category."""
    key: str
    max_tokens: float
    refill_rate: float            # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.max_tokens)
        # ``time.monotonic()`` — the same clock as ``asyncio``'s loop time,
        # but safe to call when no event loop is running (e.g. during
        # ``configure()`` at client construction time).
        self.last_refill = time.monotonic()

    def _refill(self, now: float) -> None:
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


# Notification callback signature: async def callback(message: str) -> None
NotifyCallback = Callable[[str], Awaitable[None]]


class RateLimiter:
    """
    Centralized async rate limiter for all BrsApi.ir requests.

    Every call to ``acquire()`` goes through:
      1. Daily counter   (4,000/day default — safety margin below the ~5,000/day plan cap)
      2. 5-min window    (1,000/5min default)
      3. Per-category bucket

    Usage::

        limiter = get_rate_limiter()
        await limiter.acquire("tsetmc")
    """

    def __init__(
        self,
        daily_limit: int = DEFAULT_GLOBAL_DAILY_LIMIT,
        five_min_limit: int = DEFAULT_GLOBAL_5MIN_LIMIT,
        fail_fast: bool = False,
    ) -> None:
        self._fail_fast = fail_fast
        self._buckets: dict[str, Bucket] = {}
        self._lock = asyncio.Lock()
        self._default_max_tokens = 30.0
        self._default_refill_rate = 0.5

        # ── Global counters ─────────────────────
        self._daily_limit = daily_limit
        self._five_min_limit = five_min_limit
        self._daily_count: int = 0
        self._daily_date: str = ""
        self._5min_window: deque[float] = deque()

        # ── Notification ────────────────────────
        self._notify_callbacks: list[NotifyCallback] = []
        self._notified_thresholds: set[int] = set()

        # ── Per-endpoint tracking ───────────────
        self._endpoint_counts: dict[str, int] = {}

    # ── Notification ──────────────────────────────

    def on_threshold(self, callback: NotifyCallback) -> None:
        """Register a callback fired when daily usage hits a threshold."""
        self._notify_callbacks.append(callback)

    async def _fire_notification(self, message: str) -> None:
        """Send notification to all registered callbacks."""
        for cb in self._notify_callbacks:
            try:
                await cb(message)
            except Exception:
                logger.exception("Rate limit notification callback failed")

    def _check_daily_thresholds(self) -> None:
        """Check if daily usage has crossed any notification threshold."""
        if self._daily_limit <= 0:
            return
        pct = (self._daily_count / self._daily_limit) * 100
        for threshold in sorted(NOTIFY_THRESHOLDS):
            if pct >= threshold and threshold not in self._notified_thresholds:
                self._notified_thresholds.add(threshold)
                msg = (
                    f"BrsApi rate limit alert: daily usage at {threshold}% "
                    f"({self._daily_count}/{self._daily_limit} requests). "
                    f"Remaining: {max(0, self._daily_limit - self._daily_count)}"
                )
                logger.warning(msg)
                # Fire async notification (best effort, outside lock)
                asyncio.get_event_loop().call_soon(
                    asyncio.ensure_future,
                    self._fire_notification(msg),
                )

    # ── Global limit checks ─────────────────────

    def _reset_daily_if_needed(self) -> None:
        """Reset the daily counter when a new Tehran-timezone day starts."""
        today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
        if today != self._daily_date:
            old_count = self._daily_count
            self._daily_count = 0
            self._daily_date = today
            self._notified_thresholds.clear()
            if old_count > 0:
                logger.info(
                    "BrsApi daily counter reset (previous day: %d requests)",
                    old_count,
                )

    def _prune_5min_window(self, now: float) -> None:
        """Remove timestamps older than 5 minutes from the sliding window.

        Uses ``<=`` (not ``<``): a request recorded exactly 300s ago has
        aged out of the window and must be pruned, otherwise the window can
        briefly hold limit+1 entries at the exact boundary (found by
        scripts/simulate_brsapi_usage.py).
        """
        cutoff = now - FIVE_MINUTES_SECONDS
        while self._5min_window and self._5min_window[0] <= cutoff:
            self._5min_window.popleft()

    def _wait_time_for_global_limits(self) -> float:
        """Return seconds to wait before the next request is allowed."""
        now = time.monotonic()
        self._prune_5min_window(now)

        # Daily limit
        if self._daily_count >= self._daily_limit:
            now_tz = datetime.now(TEHRAN_TZ)
            midnight = (now_tz + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            wait = (midnight - now_tz).total_seconds()
            logger.warning(
                "BrsApi DAILY LIMIT REACHED (%d/%d). Blocking until midnight Tehran.",
                self._daily_count, self._daily_limit,
            )
            return max(wait, 1.0)

        # 5-minute sliding window limit
        if len(self._5min_window) >= self._five_min_limit:
            oldest = self._5min_window[0]
            wait = (oldest + FIVE_MINUTES_SECONDS) - now
            if wait > 0:
                logger.warning(
                    "BrsApi 5-MIN LIMIT REACHED (%d/%d). Waiting %.1fs.",
                    len(self._5min_window), self._five_min_limit, wait,
                )
                return wait

        return 0.0

    def _record_request(self, endpoint: str = "") -> None:
        """Record a request in global counters."""
        self._reset_daily_if_needed()
        self._daily_count += 1
        now = time.monotonic()
        self._5min_window.append(now)
        # Track per-endpoint
        if endpoint:
            self._endpoint_counts[endpoint] = self._endpoint_counts.get(endpoint, 0) + 1
        # Check notification thresholds
        self._check_daily_thresholds()

    # ── Public API ──────────────────────────────

    def configure(self, key: str, requests_per_minute: int) -> None:
        """Set the rate limit for a given category."""
        if key in self._buckets:
            bucket = self._buckets[key]
            now = time.monotonic()
            bucket._refill(now)
            bucket.max_tokens = float(requests_per_minute)
            bucket.refill_rate = requests_per_minute / 60.0
        else:
            self._buckets[key] = Bucket(
                key=key,
                max_tokens=float(requests_per_minute),
                refill_rate=requests_per_minute / 60.0,
            )

    async def acquire(self, key: str, tokens: int = 1, endpoint: str = "", fail_fast: bool | None = None) -> None:
        """
        Acquire tokens, enforcing ALL three layers of rate limits.

        Args:
            key: Category name (e.g. "tsetmc", "codal").
            tokens: Number of tokens to consume.
            endpoint: Endpoint path for per-endpoint tracking.
            fail_fast: When True, raise ``RateLimitExhaustedError`` as soon as
                the daily budget is used up instead of sleeping until Tehran
                midnight. Defaults to the limiter's ``fail_fast`` setting
                (seeded from ``BRSAPI_FAIL_FAST_ON_DAILY_EXHAUSTED``), so every
                caller — including direct ``acquire()`` users like
                ``HistoryFetchService`` — is protected, not just the client.
        """
        if fail_fast is None:
            fail_fast = self._fail_fast

        # ── Layer 1 & 2: Global limits ──────────
        while True:
            async with self._lock:
                self._reset_daily_if_needed()
                if fail_fast and self._daily_count >= self._daily_limit:
                    raise RateLimitExhaustedError(
                        f"BrsApi daily budget exhausted ({self._daily_count}/"
                        f"{self._daily_limit}) — request rejected to protect the key"
                    )
                wait = self._wait_time_for_global_limits()
                if wait <= 0:
                    break
            # Sleep outside the lock so other tasks aren't blocked
            await asyncio.sleep(min(wait, 10.0))

        # ── Layer 3: Per-category token bucket ──
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                self.configure(key, int(self._default_refill_rate * 60))
                bucket = self._buckets[key]

            now = time.monotonic()
            bucket._refill(now)

            if bucket.max_tokens <= 0:
                self._record_request(endpoint)
                return

            if bucket.tokens >= tokens:
                bucket.tokens -= tokens
                self._record_request(endpoint)
                return

            deficit = tokens - bucket.tokens
            wait_seconds = deficit / bucket.refill_rate
            logger.debug("Rate limited %s: waiting %.2fs", key, wait_seconds)

        await asyncio.sleep(wait_seconds)

        # Re-check the global limits before consuming — another task may have
        # taken the last daily/5-min slot while we were waiting for the bucket
        # to refill. Without this re-check, concurrent callers (e.g. the
        # realtime jobs racing the nightly backfills) could slip a few
        # requests past the daily cap — exactly what the usage simulator
        # (scripts/simulate_brsapi_usage.py, fuzz scenario) found. Loop (no
        # recursion) so the lock is always released before sleeping.
        while True:
            async with self._lock:
                self._reset_daily_if_needed()
                if fail_fast and self._daily_count >= self._daily_limit:
                    raise RateLimitExhaustedError(
                        f"BrsApi daily budget exhausted ({self._daily_count}/"
                        f"{self._daily_limit}) — request rejected to protect the key"
                    )
                wait2 = self._wait_time_for_global_limits()
                if wait2 <= 0:
                    break
            await asyncio.sleep(min(wait2, 10.0))

        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket:
                now = time.monotonic()
                bucket._refill(now)
                bucket.tokens = max(0.0, bucket.tokens - tokens)
            self._record_request(endpoint)

    # ── Status / Dashboard ─────────────────────

    def status(self) -> dict[str, Any]:
        """Full status snapshot for monitoring/dashboard."""
        self._reset_daily_if_needed()
        now = time.monotonic()
        self._prune_5min_window(now)
        return {
            "global": {
                "daily_count": self._daily_count,
                "daily_limit": self._daily_limit,
                "daily_remaining": max(0, self._daily_limit - self._daily_count),
                "daily_used_pct": round(
                    (self._daily_count / self._daily_limit * 100) if self._daily_limit else 0, 1
                ),
                "5min_count": len(self._5min_window),
                "5min_limit": self._five_min_limit,
                "5min_remaining": max(0, self._five_min_limit - len(self._5min_window)),
                "5min_used_pct": round(
                    (len(self._5min_window) / self._five_min_limit * 100) if self._five_min_limit else 0, 1
                ),
            },
            "per_endpoint": dict(
                sorted(self._endpoint_counts.items(), key=lambda x: -x[1])
            ),
            "per_category": {
                key: self.get_bucket_status(key) or {}
                for key in self._buckets
            },
            "tehran_time": datetime.now(TEHRAN_TZ).isoformat(),
        }

    def get_bucket_status(self, key: str) -> dict[str, Any] | None:
        bucket = self._buckets.get(key)
        if bucket is None:
            return None
        return {
            "key": bucket.key,
            "max_tokens": bucket.max_tokens,
            "current_tokens": round(bucket.tokens, 1),
            "refill_rate": round(bucket.refill_rate, 3),
        }

    def all_bucket_status(self) -> dict[str, Any]:
        """Return a combined snapshot of global and per-category rate limits."""
        status = self.status()
        return {
            "global": status.get("global", {}),
            "per_category": {
                key: self.get_bucket_status(key) or {}
                for key in self._buckets
            },
        }

    # ── Context manager ────────────────────────

    def limit(self, key: str, tokens: int = 1) -> RateLimitContext:
        return RateLimitContext(limiter=self, key=key, tokens=tokens)


class RateLimitContext:
    def __init__(self, limiter: RateLimiter, key: str, tokens: int = 1) -> None:
        self._limiter = limiter
        self._key = key
        self._tokens = tokens

    async def __aenter__(self) -> None:
        await self._limiter.acquire(self._key, self._tokens)

    async def __aexit__(self, *args: Any) -> None:
        pass


# ── Global singleton ──────────────────────────────

_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        try:
            from brsapi.config import settings as brsapi_settings
            daily = brsapi_settings.global_daily_limit
            five_min = brsapi_settings.global_5min_limit
            fail_fast = brsapi_settings.fail_fast_on_daily_exhausted
        except Exception:
            daily = DEFAULT_GLOBAL_DAILY_LIMIT
            five_min = DEFAULT_GLOBAL_5MIN_LIMIT
            fail_fast = False
        _rate_limiter = RateLimiter(
            daily_limit=daily, five_min_limit=five_min, fail_fast=fail_fast
        )
    return _rate_limiter
