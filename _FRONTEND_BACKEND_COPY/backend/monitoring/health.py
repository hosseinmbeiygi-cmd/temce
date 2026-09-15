from __future__ import annotations

from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


CheckFn = Callable[[], Coroutine[Any, Any, HealthStatus]]


class HealthChecker:
    def __init__(self) -> None:
        self._checks: dict[str, CheckFn] = {}
        self._results: dict[str, HealthStatus] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_check("database", self._check_database)
        self.register_check("cache", self._check_cache)
        self.register_check("queue", self._check_queue)

    def register_check(self, name: str, check_fn: CheckFn) -> None:
        self._checks[name] = check_fn

    async def check_component(self, name: str, check_fn: CheckFn) -> HealthStatus:
        try:
            status = await check_fn()
            self._results[name] = status
            return status
        except Exception as e:
            self._results[name] = HealthStatus.UNHEALTHY
            logger.error("Health check failed for %s: %s", name, e)
            return HealthStatus.UNHEALTHY

    async def check_all(self) -> dict[str, HealthStatus]:
        results: dict[str, HealthStatus] = {}
        for name, check_fn in self._checks.items():
            results[name] = await self.check_component(name, check_fn)
        self._results = results
        return dict(results)

    def get_overall_status(self) -> HealthStatus:
        if not self._results:
            return HealthStatus.UNHEALTHY
        if all(s == HealthStatus.HEALTHY for s in self._results.values()):
            return HealthStatus.HEALTHY
        if any(s == HealthStatus.UNHEALTHY for s in self._results.values()):
            return HealthStatus.UNHEALTHY
        return HealthStatus.DEGRADED

    async def _check_database(self) -> HealthStatus:
        from sqlalchemy import text

        from core.database import engine

        if engine is None:
            return HealthStatus.UNHEALTHY
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return HealthStatus.HEALTHY

    async def _check_cache(self) -> HealthStatus:
        try:
            from redis.asyncio import from_url

            from core.config import settings

            r = await from_url(settings.redis_url, socket_connect_timeout=3)
            await r.ping()
            await r.aclose()
            return HealthStatus.HEALTHY
        except Exception as e:
            logger.warning("Cache health check failed: %s", e)
            return HealthStatus.DEGRADED

    async def _check_queue(self) -> HealthStatus:
        try:
            from redis.asyncio import from_url

            from core.config import settings

            r = await from_url(settings.redis_url, socket_connect_timeout=3)
            await r.ping()
            await r.aclose()
            return HealthStatus.HEALTHY
        except Exception as e:
            logger.warning("Queue health check failed: %s", e)
            return HealthStatus.DEGRADED


health_checker = HealthChecker()
