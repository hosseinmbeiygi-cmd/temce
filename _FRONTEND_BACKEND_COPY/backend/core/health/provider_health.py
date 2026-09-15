from __future__ import annotations

from core.constants import ProviderHealth
from core.health import HealthRegistry, HealthStatus, get_health_registry
from core.logging import get_logger

logger = get_logger(__name__)


class ProviderHealthCheck:
    def __init__(self, registry: HealthRegistry | None = None) -> None:
        self._registry = registry or get_health_registry()

    async def check_provider(
        self, provider_name: str, is_healthy: bool, latency_ms: float = 0.0, message: str = ""
    ) -> HealthStatus:
        status = ProviderHealth.HEALTHY if is_healthy else ProviderHealth.DOWN
        if is_healthy and latency_ms > 5000:
            status = ProviderHealth.DEGRADED
        hs = HealthStatus(
            status=status,
            component=f"provider_{provider_name}",
            message=message or f"Provider {provider_name} is {status.value}",
            details={"latency_ms": latency_ms},
        )
        self._registry.register(f"provider_{provider_name}", lambda: hs)
        return hs

    async def check_all(self) -> dict[str, HealthStatus]:
        return await self._registry.run_all()
