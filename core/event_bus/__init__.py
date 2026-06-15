from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event: str, handler: EventHandler) -> None:
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: EventHandler) -> None:
        handlers = self._handlers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: str, **data: Any) -> None:
        handlers = self._handlers.get(event, [])
        if not handlers:
            return
        logger.debug("Event %s published to %d handlers", event, len(handlers))
        tasks = [h(**data) for h in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    def clear(self) -> None:
        self._handlers.clear()


event_bus = EventBus()
