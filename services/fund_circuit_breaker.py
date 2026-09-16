"""⚡ Fund-Level Circuit Breaker & Failure Quarantine (A7 سوپر-پرامپت).

دو سطح محافظت:
  ۱) Circuit Breaker در سطح Provider → همان کلاینت BrsApi (از قبل موجود).
  ۲) Circuit Breaker در سطح **هر صندوق** → این ماژول: اگر یک صندوق ۵ بار
     پشت‌سرهم خطا داد، تا X دقیقه Skip می‌شود و در Quarantine/Alert ثبت
     می‌گردد؛ خطای یک صندوق هرگز اجرای کل Universe را متوقف نمی‌کند.

State در Redis نگهداری می‌شود (چند-ورکر) و در نبود Redis به حافظه پروسه
Fallback می‌کند. منطق تصمیم‌گیری خالص (``decide_state``) بدون I/O تست می‌شود.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

FAILURE_THRESHOLD = int(os.getenv("FUND_CB_FAILURE_THRESHOLD", "5"))
OPEN_SECONDS = float(os.getenv("FUND_CB_OPEN_SECONDS", "900"))       # ۱۵ دقیقه
WINDOW_SECONDS = float(os.getenv("FUND_CB_WINDOW_SECONDS", "600"))   # ۱۰ دقیقه


@dataclass
class BreakerState:
    """وضعیت Breaker یک صندوق."""

    failures: int = 0
    first_failure_at: float = 0.0
    open_until: float = 0.0
    last_error: str = ""
    trips: int = 0

    @property
    def is_open(self) -> bool:
        return self.open_until > time.time()


def decide_state(state: BreakerState, *, success: bool, now: float) -> BreakerState:
    """گذار حالت Breaker (Pure — بدون I/O، قابل تست).

    - شکست در پنجره پنجره مجاز، شمارنده را بالا می‌برد؛ در آستانه → Open.
    - موفقیت → Reset کامل.
    - خارج از پنجره → شمارش از نو.
    """
    if success:
        return BreakerState(failures=0, first_failure_at=0.0, open_until=0.0, trips=state.trips)
    failures = state.failures
    first = state.first_failure_at or now
    if now - first > WINDOW_SECONDS:
        failures = 0
        first = now
    failures += 1
    if failures >= FAILURE_THRESHOLD:
        return BreakerState(
            failures=failures,
            first_failure_at=first,
            open_until=now + OPEN_SECONDS,
            last_error=state.last_error,
            trips=state.trips + 1,
        )
    return BreakerState(
        failures=failures,
        first_failure_at=first,
        open_until=state.open_until,
        last_error=state.last_error,
        trips=state.trips,
    )


class FundCircuitBreaker:
    """Breaker سطح صندوق با Backend قابل تنظیم (Redis → حافظه)."""

    KEY_PREFIX = "fund:breaker:"

    def __init__(self, redis_url: str | None = None, redis_client: Any = None) -> None:
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis_client
        self._tried_redis = redis_client is not None
        self._memory: dict[str, BreakerState] = {}

    async def _get_redis(self) -> Any | None:
        if self._tried_redis:
            return self._redis
        self._tried_redis = True
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(self._redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
        except Exception:  # noqa: BLE001 — Redis اختیاری است
            self._redis = None
        return self._redis

    async def _load(self, fund_id: str) -> BreakerState:
        redis = await self._get_redis()
        if redis is None:
            return self._memory.get(fund_id, BreakerState())
        try:
            raw = await redis.get(self.KEY_PREFIX + fund_id)
            if not raw:
                return BreakerState()
            data = json.loads(raw)
            return BreakerState(
                failures=int(data.get("failures", 0)),
                first_failure_at=float(data.get("first_failure_at", 0.0)),
                open_until=float(data.get("open_until", 0.0)),
                last_error=str(data.get("last_error", ""))[:200],
                trips=int(data.get("trips", 0)),
            )
        except Exception:  # noqa: BLE001
            return self._memory.get(fund_id, BreakerState())

    async def _save(self, fund_id: str, state: BreakerState) -> None:
        self._memory[fund_id] = state
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            ttl = max(int(OPEN_SECONDS), 60) * 2
            await redis.set(
                self.KEY_PREFIX + fund_id,
                json.dumps(
                    {
                        "failures": state.failures,
                        "first_failure_at": state.first_failure_at,
                        "open_until": state.open_until,
                        "last_error": state.last_error[:200],
                        "trips": state.trips,
                    }
                ),
                ex=ttl,
            )
        except Exception:  # noqa: BLE001
            logger.debug("Breaker state persist failed for %s", fund_id)

    # ── API ──────────────────────────────────────────────────────────────

    async def allow(self, fund_id: str) -> bool:
        """آیا تماس با Provider برای این صندوق مجاز است؟"""
        state = await self._load(fund_id)
        if state.open_until and state.open_until > time.time():
            return False
        return True

    async def record_failure(self, fund_id: str, error: str = "") -> BreakerState:
        state = await self._load(fund_id)
        state.last_error = (error or "")[:200]
        new = decide_state(state, success=False, now=time.time())
        if new.open_until > state.open_until:
            logger.warning(
                "Fund circuit OPEN for %s (failures=%s, cooldown=%.0fs): %s",
                fund_id, new.failures, OPEN_SECONDS, state.last_error,
            )
        await self._save(fund_id, new)
        return new

    async def record_success(self, fund_id: str) -> None:
        state = await self._load(fund_id)
        if state.failures or state.open_until:
            await self._save(fund_id, decide_state(state, success=True, now=time.time()))

    async def status(self, fund_id: str) -> dict[str, Any]:
        state = await self._load(fund_id)
        return {
            "fund_id": fund_id,
            "failures": state.failures,
            "is_open": state.is_open,
            "open_seconds_left": max(0.0, state.open_until - time.time()) if state.open_until else 0.0,
            "trips": state.trips,
            "last_error": state.last_error or None,
        }

    async def open_funds(self) -> list[str]:
        """صندوق‌هایی که همین حالا Open هستند (برای UI/Alert)."""
        now = time.time()
        out: list[str] = []
        for fid, st in self._memory.items():
            if st.open_until > now:
                out.append(fid)
        redis = await self._get_redis()
        if redis is not None:
            try:
                async for key in redis.scan_iter(match=self.KEY_PREFIX + "*", count=200):
                    try:
                        data = json.loads(await redis.get(key) or "{}")
                        if float(data.get("open_until", 0.0)) > now:
                            out.append(key[len(self.KEY_PREFIX):])
                    except Exception:  # noqa: BLE001
                        continue
            except Exception:  # noqa: BLE001
                pass
        return sorted(set(out))


_shared_breaker: FundCircuitBreaker | None = None


def get_fund_breaker() -> FundCircuitBreaker:
    global _shared_breaker
    if _shared_breaker is None:
        _shared_breaker = FundCircuitBreaker()
    return _shared_breaker
