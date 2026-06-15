from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.constants import ProviderHealth


@dataclass
class HealthStatus:
    status: ProviderHealth
    component: str
    message: str = ""
    timestamp: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


class HealthRegistry:
    def __init__(self) -> None:
        self._checks: dict[str, Callable[[], Coroutine[Any, Any, HealthStatus]]] = {}

    def register(self, name: str, check_fn: Callable[[], Coroutine[Any, Any, HealthStatus]]) -> None:
        self._checks[name] = check_fn

    async def run_all(self) -> dict[str, HealthStatus]:
        results: dict[str, HealthStatus] = {}
        for name, check in self._checks.items():
            try:
                results[name] = await check()
            except Exception as e:
                results[name] = HealthStatus(
                    status=ProviderHealth.UNKNOWN,
                    component=name,
                    message=str(e),
                )
        return results

    async def run(self, name: str) -> HealthStatus:
        check = self._checks.get(name)
        if not check:
            return HealthStatus(status=ProviderHealth.UNKNOWN, component=name, message="No check registered")
        return await check()


_health_registry = HealthRegistry()


def get_health_registry() -> HealthRegistry:
    return _health_registry


async def health_check_all() -> dict[str, HealthStatus]:
    return await _health_registry.run_all()
