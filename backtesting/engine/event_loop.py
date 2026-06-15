from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from backtesting.engine.clock import Clock
from core.logging import get_logger

logger = get_logger(__name__)


class EventLoop:
    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock or Clock()
        self._handlers: dict[str, list[Callable]] = {}
        self._running = False

    def on(self, event_type: str, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def emit(self, event_type: str, data: Any = None) -> None:
        for handler in self._handlers.get(event_type, []):
            await handler(data) if callable(handler) else None

    async def run(self, bars: list[dict[str, Any]]) -> None:
        self._running = True
        for bar in bars:
            if not self._running:
                break
            self.clock.tick(timedelta(days=1))
            await self.emit("bar", bar)
            if "prices" in bar:
                await self.emit("market_data", bar)

    def stop(self) -> None:
        self._running = False

    def reset(self) -> None:
        self.clock.reset()
        self._handlers.clear()
        self._running = False
