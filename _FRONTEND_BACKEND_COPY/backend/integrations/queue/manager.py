from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class QueueManager:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}
        self._local_queue: list[dict[str, Any]] = []

    def register_handler(self, queue_name: str, handler: Callable[..., Coroutine[Any, Any, Any]]) -> None:
        self._handlers[queue_name] = handler

    async def publish(self, queue_name: str, message: Any) -> None:
        self._local_queue.append({"queue": queue_name, "message": message, "handler": self._handlers.get(queue_name)})
        logger.info("Published message to %s", queue_name)

    async def consume_all(self) -> None:
        while self._local_queue:
            item = self._local_queue.pop(0)
            handler = item.get("handler")
            if handler:
                try:
                    await handler(item["message"])
                except Exception as e:
                    logger.error("Queue handler failed: %s", e)

    async def close(self) -> None:
        self._local_queue.clear()
