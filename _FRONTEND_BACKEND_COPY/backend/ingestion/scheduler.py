from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from typing import Any

from core.logging import get_logger

from .config import IngestionConfig

logger = get_logger(__name__)


class MarketScheduler:
    def __init__(self, config: IngestionConfig) -> None:
        self._config = config
        self._running = False
        self._tasks: list[asyncio.Task[Any]] = []
        self._callbacks: list[Any] = []

    def on_tick(self, callback: Any) -> None:
        self._callbacks.append(callback)

    async def start(self) -> None:
        self._running = True
        self._tasks.append(asyncio.create_task(self._run_loop()))
        logger.info("Scheduler started (interval=%ds)", self._config.scheduler_interval_seconds)

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Scheduler stopped")

    async def _run_loop(self) -> None:
        while self._running:
            if self._in_market_hours():
                for cb in self._callbacks:
                    try:
                        await cb()
                    except Exception:
                        logger.exception("Scheduler callback failed")
            else:
                logger.debug("Outside market hours, skipping tick")
            await asyncio.sleep(self._config.scheduler_interval_seconds)

    def _in_market_hours(self) -> bool:
        if not self._config.market_hours_enabled:
            return True
        tz = timezone(timedelta(hours=3, minutes=30))
        now = datetime.now(tz).time()
        open_t = time.fromisoformat(self._config.market_open)
        close_t = time.fromisoformat(self._config.market_close)
        if open_t <= close_t:
            return open_t <= now <= close_t
        return now >= open_t or now <= close_t
