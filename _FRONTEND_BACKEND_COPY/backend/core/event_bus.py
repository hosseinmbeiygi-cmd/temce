from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from core.events import DomainEvent
from core.logging import get_logger

logger = get_logger(__name__)

Handler = Callable[..., Any]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._handlers[event_type].append(handler)
        logger.debug("Handler subscribed to %s", event_type)

    def unsubscribe(self, event_type: str, handler: Handler) -> None:
        try:
            self._handlers[event_type].remove(handler)
        except ValueError:
            logger.debug("Handler not subscribed to %s (no-op)", event_type)
        logger.debug("Handler unsubscribed from %s", event_type)

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribed handlers.

        Handlers run in subscription order; one failing handler does **not**
        prevent the remaining handlers from running (each is isolated).
        """
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                logger.exception("Event handler %r failed for %s", handler, event.event_type)

    def clear(self) -> None:
        self._handlers.clear()


event_bus = EventBus()
