from __future__ import annotations

import asyncio

from core.config import settings
from core.logging import get_logger

from ingestion.market_scan_service import MarketScanService

logger = get_logger(__name__)


class IngestionWorkerApp:
    def __init__(self) -> None:
        self._service = MarketScanService()

    async def start(self) -> None:
        logger.info("Ingestion worker started")
        await self._service.start()
        await self._service.run()

    async def stop(self) -> None:
        await self._service.stop()
        logger.info("Ingestion worker stopped")

    async def status(self) -> dict:
        return await self._service.status()

