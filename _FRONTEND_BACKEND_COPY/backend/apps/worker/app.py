from __future__ import annotations

import asyncio

from apps.worker.consumer import WorkerConsumer
from apps.worker.error_policy import ErrorPolicy
from core.logging import get_logger

logger = get_logger(__name__)


class WorkerApp:
    def __init__(self) -> None:
        self._running = False
        self.consumer = WorkerConsumer()
        self.error_policy = ErrorPolicy()

    async def start(self) -> None:
        self._running = True
        logger.info("Worker started")

        # Connect Redis in the background so JobQueueConsumer + JobLocking
        # use the distributed backend. Non-blocking: until the connection is
        # ready the consumer idles and the scheduler falls back to in-process.
        try:
            from core.cache import get_cache

            await get_cache().initialize()
        except Exception:
            logger.warning("Redis cache init failed; worker falls back to idle mode")

        await self.consumer.start()
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        await self.consumer.stop()
        logger.info("Worker stopped")
