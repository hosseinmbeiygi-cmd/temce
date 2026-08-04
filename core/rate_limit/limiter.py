from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class RateLimiter:
    """Sliding-window rate limiter.

    Each key has a window_seconds (default 60s) and a burst (max requests per window).
    Tokens older than the window are pruned on each check.
    """

    def __init__(self) -> None:
        self._limits: dict[str, tuple[float, int, float, float, list[float]]] = {}

    def set_limit(self, key: str, rate: float, burst: int = 1, window_seconds: float = 60.0) -> None:
        """Register a rate limit for a key.

        Args:
            key: Unique identifier (e.g. "api:127.0.0.1:/api/v1/signals").
            rate: Requests per second (used for acquire/wait calculations).
            burst: Maximum requests allowed in the window.
            window_seconds: Sliding window duration in seconds.
        """
        self._limits[key] = (rate, burst, window_seconds, time.monotonic(), [])

    def has_limit(self, key: str) -> bool:
        """Check if a rate limit is registered for the given key."""
        return key in self._limits

    def allow(self, key: str) -> bool:
        """Check whether a request is allowed under the sliding window."""
        if key not in self._limits:
            return True
        rate, burst, window_seconds, _, tokens = self._limits[key]
        now = time.monotonic()
        cutoff = now - window_seconds
        tokens = [t for t in tokens if t > cutoff]
        if len(tokens) < burst:
            tokens.append(now)
            self._limits[key] = (rate, burst, window_seconds, now, tokens)
            return True
        return False

    def remaining(self, key: str) -> int:
        """Return the number of remaining allowed requests in the current window."""
        if key not in self._limits:
            return 999
        rate, burst, window_seconds, _, tokens = self._limits[key]
        now = time.monotonic()
        cutoff = now - window_seconds
        active = sum(1 for t in tokens if t > cutoff)
        return max(0, burst - active)

    async def acquire(self, key: str) -> float:
        if key not in self._limits:
            return 0.0
        rate, burst, window_seconds, _, tokens = self._limits[key]
        now = time.monotonic()
        cutoff = now - window_seconds
        tokens = [t for t in tokens if t > cutoff]
        if len(tokens) < burst:
            tokens.append(now)
            self._limits[key] = (rate, burst, window_seconds, now, tokens)
            return 0.0
        wait = 1.0 / rate
        await asyncio.sleep(wait)
        self._limits[key] = (rate, burst, window_seconds, now, tokens[1:] + [now + wait])
        return wait

    async def limit(self, key: str, coro: Callable[[], Coroutine[Any, Any, T]]) -> T:
        await self.acquire(key)
        return await coro()

    def wrap(self, key: str, rate: float, burst: int | None = None) -> Callable:
        """Decorator that rate-limits a callable.

        ``rate`` is interpreted as *requests per minute* (matching the
        ``*_rate_limit_per_minute`` settings). ``burst`` defaults to the
        per-minute rate rounded up so a freshly registered key doesn't
        accidentally lock itself out immediately.

        Note: this is a minute-based convenience wrapper; the underlying
        ``set_limit`` treats ``rate`` as requests-per-second for
        ``acquire()`` wait-time calculations, so the effective smoothing
        here is 1s/rate. For precise sub-minute throttling use
        ``set_limit``/``acquire`` directly.
        """
        burst = burst or max(1, int(rate))
        self.set_limit(key, rate=rate / 60.0, burst=burst, window_seconds=60.0)

        def decorator(func: Callable) -> Callable:
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                await self.acquire(key)
                return await func(*args, **kwargs)

            return wrapper

        return decorator


_global_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _global_limiter


async def throttle(key: str, rate: float) -> None:
    await _global_limiter.acquire(key)
