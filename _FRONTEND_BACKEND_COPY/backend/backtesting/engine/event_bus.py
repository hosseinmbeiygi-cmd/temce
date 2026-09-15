from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from backtesting.engine.event_builder import MarketEvent
from core.logging import get_logger

logger = get_logger(__name__)

EventHandler = Callable[[MarketEvent], Any]


class EventBus:
    """Lightweight publish/subscribe hub for market events.

    Components subscribe to event types and get notified when events are published.
    This decouples the Replay Engine from the downstream consumers.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[MarketEvent] = []
        self._max_history: int = 1000

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type.

        Args:
            event_type: Event type string (e.g., 'TRADE', 'QUOTE') or '*' for all
            handler: Callable that takes a MarketEvent
        """
        self._subscribers[event_type].append(handler)
        logger.debug("Handler subscribed to %s", event_type)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all event types."""
        self.subscribe("*", handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler subscription."""
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    def publish(self, event: MarketEvent) -> None:
        """Publish an event to all matching subscribers.

        Args:
            event: The MarketEvent to publish
        """
        # Store in history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # Notify type-specific subscribers
        event_type = str(event.event_type)
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error("EventBus handler error for %s: %s", event_type, e)

        # Notify catch-all subscribers
        for handler in self._subscribers.get("*", []):
            try:
                handler(event)
            except Exception as e:
                logger.error("EventBus catch-all handler error: %s", e)

    def publish_batch(self, events: list[MarketEvent]) -> None:
        """Publish multiple events in sequence."""
        for event in events:
            self.publish(event)

    def clear(self) -> None:
        """Remove all subscribers and history."""
        self._subscribers.clear()
        self._history.clear()

    @property
    def subscriber_count(self) -> int:
        return sum(len(h) for h in self._subscribers.values())

    @property
    def recent_events(self) -> list[MarketEvent]:
        return list(self._history)
