from __future__ import annotations

from core.constants import ProviderHealth
from core.health import HealthRegistry, HealthStatus, get_health_registry


class LivenessCheck:
    def __init__(self, registry: HealthRegistry | None = None) -> None:
        self._registry = registry or get_health_registry()

    def register_defaults(self) -> None:
        self._registry.register("app_liveness", self._check_app_liveness)

    async def _check_app_liveness(self) -> HealthStatus:
        return HealthStatus(
            status=ProviderHealth.HEALTHY,
            component="app_liveness",
            message="Application is running",
        )

    async def check(self) -> HealthStatus:
        return await self._registry.run("app_liveness")

    async def check_all(self) -> dict[str, HealthStatus]:
        return await self._registry.run_all()
