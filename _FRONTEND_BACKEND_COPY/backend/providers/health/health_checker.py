from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger

logger = get_logger(__name__)


class HealthChecker:
    def __init__(self) -> None:
        self._checks: dict[str, Any] = {}

    def register(self, name: str, check_fn: Any) -> None:
        self._checks[name] = check_fn

    async def check(self, name: str) -> dict[str, Any]:
        if name not in self._checks:
            return {"status": ProviderHealth.UNKNOWN, "message": "No check registered"}
        try:
            result = await self._checks[name]()
            return {"status": ProviderHealth.HEALTHY if result else ProviderHealth.DOWN, "message": str(result)}
        except Exception as e:
            logger.error("Health check %s failed: %s", name, e)
            return {"status": ProviderHealth.DOWN, "message": str(e)}

    async def check_all(self) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for name in self._checks:
            results[name] = await self.check(name)
        return results
