from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.logging import get_logger
from integrations.queue.broker import Broker, Message

logger = get_logger(__name__)


class Consumer:
    def __init__(self, broker: Broker, queue_name: str, prefetch_count: int = 1):
        self._broker = broker
        self._queue_name = queue_name
        self._prefetch_count = prefetch_count
        self._handler: Callable | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    async def register(self, handler: Callable) -> None:
        self._handler = handler
        await self._broker.consume(self._queue_name, self._handle)

    async def _handle(self, message: Message) -> None:
        if self._handler is None:
            logger.warning("No handler registered for queue %s", self._queue_name)
            return
        try:
            result = self._handler(message)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error("Consumer error on %s: %s", self._queue_name, e)

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    @property
    def queue_name(self) -> str:
        return self._queue_name
