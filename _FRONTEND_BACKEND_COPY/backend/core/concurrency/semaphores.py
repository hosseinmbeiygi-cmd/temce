from __future__ import annotations

import asyncio
from typing import Any, TypeVar

from core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


class AdaptiveSemaphore:
    def __init__(self, max_concurrent: int = 10, min_concurrent: int = 1) -> None:
        self._max = max_concurrent
        self._min = min_concurrent
        self._current = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        await self._semaphore.acquire()

    def release(self) -> None:
        self._semaphore.release()

    async def __aenter__(self) -> AdaptiveSemaphore:
        await self.acquire()
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.release()

    async def adjust(self, target: int) -> None:
        async with self._lock:
            target = max(self._min, min(target, self._max))
            diff = target - self._current
            if diff > 0:
                for _ in range(diff):
                    self._semaphore.release()
            elif diff < 0:
                for _ in range(-diff):
                    await self._semaphore.acquire()
            self._current = target
            logger.debug("Semaphore adjusted from %d to %d", self._current, target)

    @property
    def current(self) -> int:
        return self._current


class RateLimitingSemaphore:
    def __init__(self, rate: float, burst: int = 1) -> None:
        self._rate = rate
        self._burst = burst
        self._tokens = burst
        self._last_refill = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_refill
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens >= 1:
                self._tokens -= 1
                return
            wait = (1 - self._tokens) / self._rate if self._rate > 0 else 0
            self._tokens = 0
        if wait > 0:
            await asyncio.sleep(wait)
