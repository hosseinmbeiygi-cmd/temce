from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class RateLimiter:
    def __init__(self) -> None:
        self._limits: dict[str, tuple[float, int, float, list[float]]] = {}

    def set_limit(self, key: str, rate: float, burst: int = 1) -> None:
        self._limits[key] = (rate, burst, time.monotonic(), [])

    def allow(self, key: str) -> bool:
        if key not in self._limits:
            return True
        rate, burst, _, tokens = self._limits[key]
        now = time.monotonic()
        cutoff = now - 1.0
        tokens = [t for t in tokens if t > cutoff]
        if len(tokens) < burst:
            tokens.append(now)
            self._limits[key] = (rate, burst, now, tokens)
            return True
        return False

    async def acquire(self, key: str) -> float:
        if key not in self._limits:
            return 0.0
        rate, burst, _, tokens = self._limits[key]
        now = time.monotonic()
        cutoff = now - 1.0
        tokens = [t for t in tokens if t > cutoff]
        if len(tokens) < burst:
            tokens.append(now)
            self._limits[key] = (rate, burst, now, tokens)
            return 0.0
        wait = 1.0 / rate
        await asyncio.sleep(wait)
        self._limits[key] = (rate, burst, now, tokens[1:] + [now + wait])
        return wait

    async def limit(self, key: str, coro: Callable[[], Coroutine[Any, Any, T]]) -> T:
        await self.acquire(key)
        return await coro()

    def wrap(self, key: str, rate: float) -> Callable:
        self.set_limit(key, rate)

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
