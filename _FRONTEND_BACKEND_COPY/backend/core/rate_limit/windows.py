from __future__ import annotations

import asyncio
import time

from core.logging import get_logger

logger = get_logger(__name__)


class SlidingWindow:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._entries: list[float] = []
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            self._entries = [e for e in self._entries if e > cutoff]
            if len(self._entries) >= self.limit:
                return False
            self._entries.append(now)
            return True

    @property
    def count(self) -> int:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        return sum(1 for e in self._entries if e > cutoff)

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.count)

    def reset(self) -> None:
        self._entries.clear()


class FixedWindow:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._count = 0
        self._window_start = time.monotonic()
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            if now - self._window_start >= self.window_seconds:
                self._count = 0
                self._window_start = now
            if self._count >= self.limit:
                return False
            self._count += 1
            return True

    @property
    def remaining(self) -> int:
        now = time.monotonic()
        if now - self._window_start >= self.window_seconds:
            return self.limit
        return max(0, self.limit - self._count)

    def reset(self) -> None:
        self._count = 0
        self._window_start = time.monotonic()
