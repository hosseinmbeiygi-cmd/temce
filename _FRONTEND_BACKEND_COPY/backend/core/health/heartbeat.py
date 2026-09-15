from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class Heartbeat:
    def __init__(self, interval: float = 30.0) -> None:
        self.interval = interval
        self._last_beat: datetime | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._listeners: list[Callable[[], Coroutine[Any, Any, None]]] = []

    def on_beat(self, listener: Callable[[], Coroutine[Any, Any, None]]) -> None:
        self._listeners.append(listener)

    async def _beat_loop(self) -> None:
        while self._running:
            self._last_beat = datetime.now(UTC)
            for listener in self._listeners:
                try:
                    await listener()
                except Exception as e:
                    logger.error("Heartbeat listener error: %s", e)
            await asyncio.sleep(self.interval)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._beat_loop())
        logger.info("Heartbeat started (interval=%.1fs)", self.interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Heartbeat stopped")

    @property
    def last_beat(self) -> datetime | None:
        return self._last_beat

    @property
    def is_alive(self) -> bool:
        if self._last_beat is None:
            return False
        elapsed = (datetime.now(UTC) - self._last_beat).total_seconds()
        return elapsed < self.interval * 3
