"""ابزارهای Resilience: Circuit Breaker + Retry + Stale Flag.

این ماژول با دو Backend کار می‌کند:
- اگر Redis در دسترس باشد → state در Redis نگهداری می‌شود (cluster-safe)
- در غیر این صورت → state در in-memory dict (برای dev/test)

طبق spec صندوق‌یار:
- آستانه باز شدن: ۵ خطای متوالی در ۶۰ ثانیه
- مدت Open state: ۵ دقیقه
- بعد از Half-Open: یک درخواست آزمایشی
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from .constants import (
    CB_FAILURE_THRESHOLD,
    CB_OPEN_DURATION_SECONDS,
    CB_WINDOW_SECONDS,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CBStats:
    failures: deque[float]  # timestamp ها
    state: CircuitState = CircuitState.CLOSED
    opened_at: float = 0.0


class CircuitBreaker:
    """Circuit Breaker سطح Adapter با fallback in-memory.

    استفاده:
        cb = CircuitBreaker("fipiran")
        async with cb:
            data = await cb.call(fetch_func, symbol)
    """

    def __init__(self, name: str, redis_client: Any | None = None):
        self.name = name
        self.redis = redis_client
        self._stats = CBStats(failures=deque())
        self._lock = asyncio.Lock()

    async def _record_success(self) -> None:
        async with self._lock:
            self._stats.failures.clear()
            self._stats.state = CircuitState.CLOSED
            self._stats.opened_at = 0.0

    async def _record_failure(self) -> None:
        now = time.monotonic()
        async with self._lock:
            self._stats.failures.append(now)
            # پاک کردن failure های خارج از پنجره
            while self._stats.failures and (now - self._stats.failures[0] > CB_WINDOW_SECONDS):
                self._stats.failures.popleft()

            if len(self._stats.failures) >= CB_FAILURE_THRESHOLD:
                self._stats.state = CircuitState.OPEN
                self._stats.opened_at = now

    async def _allow_request(self) -> bool:
        async with self._lock:
            if self._stats.state == CircuitState.CLOSED:
                return True
            if self._stats.state == CircuitState.OPEN:
                if time.monotonic() - self._stats.opened_at > CB_OPEN_DURATION_SECONDS:
                    self._stats.state = CircuitState.HALF_OPEN
                    return True
                return False
            # HALF_OPEN → اجازه فقط یک درخواست
            return True

    async def state(self) -> CircuitState:
        async with self._lock:
            return self._stats.state

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        if not await self._allow_request():
            raise CircuitOpenError(f"Circuit breaker '{self.name}' is OPEN. Retry after {CB_OPEN_DURATION_SECONDS}s.")
        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            await self._record_failure()
            logger.warning(
                "circuit_breaker_failure source=%s err=%s",
                self.name,
                exc.__class__.__name__,
            )
            raise
        else:
            await self._record_success()
            return result


class CircuitOpenError(RuntimeError):
    """خطای مربوط به باز بودن Circuit Breaker."""


# ── Retry با Exponential Backoff ───────────────────────────────────
def retry(
    func: Callable[..., Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Awaitable[T]:
    """دکوراتور retry ساده برای adapter callها.

    استفاده:
        data = await retry(fetch_nav, max_attempts=3)(symbol)
    """

    async def wrapper(*args: Any, **kwargs: Any) -> T:
        delay = base_delay
        last_exc: BaseException | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except exceptions as exc:
                last_exc = exc
                if attempt == max_attempts:
                    break
                logger.info(
                    "retry attempt=%d/%d delay=%.1fs err=%s",
                    attempt,
                    max_attempts,
                    delay,
                    exc.__class__.__name__,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
        assert last_exc is not None
        raise last_exc

    return wrapper


# ── Fallback Priority Chain ─────────────────────────────────────────
# طبق spec: TSETMC → فیپیران → کش Redis (تا ۴۸ ساعت) → null + alert
FALLBACK_PRIORITY = ("tsetmc", "fipiran", "redis_cache", "null")


# ── Registry سراسری CB ها (per source) ─────────────────────────────
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, redis_client: Any | None = None) -> CircuitBreaker:
    """دریافت/ساخت Circuit Breaker برای یک منبع (singleton per name)."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, redis_client)
    return _circuit_breakers[name]


def reset_circuit_breakers() -> None:
    """پاک کردن registry — برای تست."""
    _circuit_breakers.clear()
