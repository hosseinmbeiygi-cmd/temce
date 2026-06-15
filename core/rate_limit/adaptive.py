from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from core.logging import get_logger

logger = get_logger(__name__)


class AdaptiveRateLimiter:
    def __init__(self, initial_rate: float = 60.0, min_rate: float = 5.0, max_rate: float = 200.0) -> None:
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self._success_count = 0
        self._failure_count = 0
        self._last_adjustment = time.monotonic()
        self._adjustment_interval = 10.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if now - self._last_adjustment >= self._adjustment_interval:
                self._adjust()
            wait = 1.0 / self.current_rate if self.current_rate > 0 else 1.0
            self._last_adjustment = now
        if wait > 0:
            await asyncio.sleep(wait)

    def _adjust(self) -> None:
        total = self._success_count + self._failure_count
        if total == 0:
            return
        success_rate = self._success_count / total
        if success_rate > 0.95 and self.current_rate < self.max_rate:
            self.current_rate = min(self.current_rate * 1.1, self.max_rate)
            logger.debug("Rate increased to %.1f req/s", self.current_rate)
        elif success_rate < 0.8 and self.current_rate > self.min_rate:
            self.current_rate = max(self.current_rate * 0.8, self.min_rate)
            logger.debug("Rate decreased to %.1f req/s", self.current_rate)
        self._success_count = 0
        self._failure_count = 0

    def record_success(self) -> None:
        self._success_count += 1

    def record_failure(self) -> None:
        self._failure_count += 1

    async def limit(self, coro: Callable) -> any:
        await self.acquire()
        try:
            result = await coro()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise
