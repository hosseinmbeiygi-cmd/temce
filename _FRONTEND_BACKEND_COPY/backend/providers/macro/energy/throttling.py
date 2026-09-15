from __future__ import annotations

import asyncio
import time
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class EnergyThrottle:
    def __init__(self, requests_per_minute: int = 20) -> None:
        self.requests_per_minute = requests_per_minute
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < 60.0]
            if len(self._timestamps) >= self.requests_per_minute:
                wait = 60.0 - (now - self._timestamps[0])
                if wait > 0:
                    await asyncio.sleep(wait)
            self._timestamps.append(time.monotonic())

    async def __aenter__(self) -> EnergyThrottle:
        await self.acquire()
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass
