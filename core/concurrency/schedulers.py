from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class Scheduler:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False

    async def schedule_interval(
        self, name: str, callback: Callable[[], Coroutine[Any, Any, None]], interval: float
    ) -> None:
        if name in self._tasks:
            raise RuntimeError(f"Task {name} already scheduled")

        async def loop() -> None:
            while self._running:
                try:
                    await callback()
                except Exception as e:
                    logger.error("Scheduled task %s failed: %s", name, e)
                await asyncio.sleep(interval)

        task = asyncio.create_task(loop(), name=name)
        self._tasks[name] = task
        logger.info("Scheduled interval task %s every %.2fs", name, interval)

    async def schedule_once(self, name: str, callback: Callable[[], Coroutine[Any, Any, None]], delay: float) -> None:
        async def delayed() -> None:
            await asyncio.sleep(delay)
            try:
                await callback()
            except Exception as e:
                logger.error("One-shot task %s failed: %s", name, e)

        task = asyncio.create_task(delayed(), name=name)
        self._tasks[name] = task

    async def schedule_cron(self, name: str, callback: Callable[[], Coroutine[Any, Any, None]], cron_expr: str) -> None:
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}")

        async def cron_loop() -> None:
            while self._running:
                now = datetime.now(UTC)
                next_run = self._next_cron_time(now, parts)
                wait = (next_run - now).total_seconds()
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    await callback()
                except Exception as e:
                    logger.error("Cron task %s failed: %s", name, e)

        task = asyncio.create_task(cron_loop(), name=name)
        self._tasks[name] = task

    def _next_cron_time(self, now: datetime, parts: list[str]) -> datetime:
        minute = int(parts[0]) if parts[0] != "*" else now.minute
        hour = int(parts[1]) if parts[1] != "*" else now.hour
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    async def cancel(self, name: str) -> None:
        task = self._tasks.pop(name, None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
        for name in list(self._tasks.keys()):
            await self.cancel(name)
