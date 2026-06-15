from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from typing import Any

from core.constants import ProviderHealth
from core.health import HealthRegistry, HealthStatus, get_health_registry
from core.logging import get_logger

logger = get_logger(__name__)


class HealthMonitor:
    def __init__(self, registry: HealthRegistry | None = None, interval: float = 60.0) -> None:
        self._registry = registry or get_health_registry()
        self.interval = interval
        self._results: dict[str, HealthStatus] = {}
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._callbacks: list[Callable[[dict[str, HealthStatus]], Coroutine[Any, Any, None]]] = []

    def on_check(self, callback: Callable[[dict[str, HealthStatus]], Coroutine[Any, Any, None]]) -> None:
        self._callbacks.append(callback)

    async def _monitor_loop(self) -> None:
        while self._running:
            self._results = await self._registry.run_all()
            for callback in self._callbacks:
                try:
                    await callback(self._results)
                except Exception as e:
                    logger.error("Monitor callback error: %s", e)
            await asyncio.sleep(self.interval)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitor started (interval=%.1fs)", self.interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Health monitor stopped")

    @property
    def results(self) -> dict[str, HealthStatus]:
        return dict(self._results)

    @property
    def is_healthy(self) -> bool:
        if not self._results:
            return False
        return all(s.status == ProviderHealth.HEALTHY for s in self._results.values())
