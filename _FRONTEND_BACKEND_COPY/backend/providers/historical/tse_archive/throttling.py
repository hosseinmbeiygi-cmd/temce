from __future__ import annotations

import asyncio
import time
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class TseArchiveThrottle:
    def __init__(self, requests_per_minute: int = 20, delay_between: float = 3.0) -> None:
        self.requests_per_minute = requests_per_minute
        self.delay_between = delay_between
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self.delay_between:
                await asyncio.sleep(self.delay_between - elapsed)
            self._last_request = time.monotonic()

    async def __aenter__(self) -> TseArchiveThrottle:
        await self.acquire()
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass
