from __future__ import annotations

from core.constants import ProviderHealth
from core.health import HealthRegistry, HealthStatus, get_health_registry
from core.logging import get_logger

logger = get_logger(__name__)


class SystemHealth:
    def __init__(self, registry: HealthRegistry | None = None) -> None:
        self._registry = registry or get_health_registry()

    def register_checks(self) -> None:
        self._registry.register("cpu", self._check_cpu)
        self._registry.register("memory", self._check_memory)
        self._registry.register("disk", self._check_disk)
        self._registry.register("uptime", self._check_uptime)

    async def _check_cpu(self) -> HealthStatus:
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.5)
            status = ProviderHealth.HEALTHY if cpu_percent < 80 else ProviderHealth.DEGRADED
            return HealthStatus(
                status=status,
                component="cpu",
                message=f"CPU usage: {cpu_percent}%",
                details={"cpu_percent": cpu_percent},
            )
        except ImportError:
            return HealthStatus(status=ProviderHealth.HEALTHY, component="cpu", message="psutil not available")

    async def _check_memory(self) -> HealthStatus:
        try:
            import psutil

            mem = psutil.virtual_memory()
            status = ProviderHealth.HEALTHY if mem.percent < 80 else ProviderHealth.DEGRADED
            return HealthStatus(
                status=status,
                component="memory",
                message=f"Memory usage: {mem.percent}%",
                details={"memory_percent": mem.percent, "available_mb": mem.available // (1024 * 1024)},
            )
        except ImportError:
            return HealthStatus(status=ProviderHealth.HEALTHY, component="memory", message="psutil not available")

    async def _check_disk(self) -> HealthStatus:
        try:
            import psutil

            disk = psutil.disk_usage("/")
            status = ProviderHealth.HEALTHY if disk.percent < 90 else ProviderHealth.DEGRADED
            return HealthStatus(
                status=status,
                component="disk",
                message=f"Disk usage: {disk.percent}%",
                details={"disk_percent": disk.percent, "free_gb": disk.free // (1024**3)},
            )
        except ImportError:
            return HealthStatus(status=ProviderHealth.HEALTHY, component="disk", message="psutil not available")

    async def _check_uptime(self) -> HealthStatus:
        import time

        uptime_seconds = time.monotonic()
        return HealthStatus(
            status=ProviderHealth.HEALTHY,
            component="uptime",
            message=f"Uptime: {uptime_seconds:.0f}s",
            details={"uptime_seconds": uptime_seconds},
        )

    async def check_all(self) -> dict[str, HealthStatus]:
        return await self._registry.run_all()
