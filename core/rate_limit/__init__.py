from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class TokenBucket:
    def __init__(self, rate: float, burst: int | None = None) -> None:
        self.rate = rate
        self.burst = burst or int(rate)
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0

            wait = (1.0 - self.tokens) / self.rate
            self.tokens = 0.0
            return wait


class RateLimiter:
    def __init__(self, max_calls: int = 60, window_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: list[float] = []
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    def allow(self) -> bool:
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < self.window_seconds]
        if len(self._calls) < self.max_calls:
            self._calls.append(now)
            return True
        return False

    def remaining(self) -> int:
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < self.window_seconds]
        return self.max_calls - len(self._calls)

    def __enter__(self) -> RateLimiter:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def get_bucket(self, key: str, rate: float, burst: int | None = None) -> TokenBucket:
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(rate=rate, burst=burst)
        return self._buckets[key]

    async def limit(self, key: str, rate: float, burst: int | None = None) -> None:
        bucket = self.get_bucket(key, rate, burst)
        wait = await bucket.acquire()
        if wait > 0:
            logger.debug("Rate limit wait %.2fs for %s", wait, key)
            await asyncio.sleep(wait)

    def wrap(self, key: str, rate: float) -> Callable:
        def decorator(func: Callable) -> Callable:
            async def wrapper(*args, **kwargs):
                await self.limit(key, rate)
                return await func(*args, **kwargs)

            return wrapper

        return decorator


_global_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _global_limiter


async def throttle(key: str, rate: float, burst: int | None = None) -> None:
    await _global_limiter.limit(key, rate, burst)
