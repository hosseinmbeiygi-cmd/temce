from __future__ import annotations

from typing import Any

from core.logging import get_logger
from providers.base.base_provider import BaseProvider

logger = get_logger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def register(self, name: str, provider: BaseProvider) -> None:
        self._providers[name] = provider
        logger.info("Registered provider: %s", name)

    def unregister(self, name: str) -> None:
        self._providers.pop(name, None)

    def get(self, name: str) -> BaseProvider | None:
        return self._providers.get(name)

    def list(self) -> dict[str, str]:
        return {k: v.__class__.__name__ for k, v in self._providers.items()}

    async def health_all(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for name, provider in self._providers.items():
            try:
                results[name] = await provider.health()
            except Exception as e:
                results[name] = {"healthy": False, "message": str(e)}
        return results


provider_registry = ProviderRegistry()
