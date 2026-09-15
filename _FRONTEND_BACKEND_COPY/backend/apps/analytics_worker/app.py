from __future__ import annotations

import asyncio

from core.logging import get_logger

logger = get_logger(__name__)


class AnalyticsWorkerApp:
    def __init__(self) -> None:
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Analytics worker started")
        while self._running:
            await asyncio.sleep(10)

    def stop(self) -> None:
        self._running = False
