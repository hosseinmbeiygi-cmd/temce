from __future__ import annotations

from core.constants import ProviderHealth
from core.health import HealthRegistry, HealthStatus, get_health_registry


class ReadinessCheck:
    def __init__(self, registry: HealthRegistry | None = None) -> None:
        self._registry = registry or get_health_registry()
        self._ready = False

    def mark_ready(self) -> None:
        self._ready = True

    def mark_not_ready(self) -> None:
        self._ready = False

    def register_defaults(self) -> None:
        self._registry.register("app_readiness", self._check_readiness)

    async def _check_readiness(self) -> HealthStatus:
        if self._ready:
            return HealthStatus(
                status=ProviderHealth.HEALTHY,
                component="app_readiness",
                message="Application is ready",
            )
        return HealthStatus(
            status=ProviderHealth.DEGRADED,
            component="app_readiness",
            message="Application is not ready",
        )

    async def check(self) -> HealthStatus:
        return await self._registry.run("app_readiness")

    @property
    def is_ready(self) -> bool:
        return self._ready
