from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger

logger = get_logger(__name__)


class HealthStatus:
    def __init__(self, name: str) -> None:
        self.name = name
        self.status: ProviderHealth = ProviderHealth.UNKNOWN
        self.message: str = ""
        self.last_checked: datetime | None = None
        self.latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "latency_ms": self.latency_ms,
        }


class HealthCheckRegistry:
    def __init__(self) -> None:
        self._checks: dict[str, Callable[[], Coroutine[Any, Any, HealthStatus]]] = {}

    def register(self, name: str, check_fn: Callable[[], Coroutine[Any, Any, HealthStatus]]) -> None:
        self._checks[name] = check_fn

    def unregister(self, name: str) -> None:
        self._checks.pop(name, None)

    async def run_check(self, name: str) -> HealthStatus:
        fn = self._checks.get(name)
        if not fn:
            status = HealthStatus(name)
            status.status = ProviderHealth.UNKNOWN
            status.message = "No check registered"
            return status
        return await fn()

    async def run_all(self) -> dict[str, HealthStatus]:
        results: dict[str, HealthStatus] = {}
        for name, fn in self._checks.items():
            results[name] = await fn()
        return results
