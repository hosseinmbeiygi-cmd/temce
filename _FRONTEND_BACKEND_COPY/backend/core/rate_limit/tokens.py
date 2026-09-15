from __future__ import annotations

import asyncio
import time

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

    @property
    def available(self) -> float:
        now = time.monotonic()
        elapsed = now - self.last_refill
        return min(float(self.burst), self.tokens + elapsed * self.rate)
