from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class WorkerConsumer:
    def __init__(self) -> None:
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Worker consumer started")

    async def stop(self) -> None:
        self._running = False
        logger.info("Worker consumer stopped")

    async def process_message(self, message: dict[str, Any]) -> None:
        logger.info("Processing message: %s", message.get("type", "unknown"))
