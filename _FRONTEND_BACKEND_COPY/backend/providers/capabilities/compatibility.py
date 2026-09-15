from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


class ProviderCompatibility:
    def __init__(self) -> None:
        self._compat: dict[str, set[str]] = {}

    def declare_compatible(self, provider_a: str, provider_b: str) -> None:
        self._compat.setdefault(provider_a, set()).add(provider_b)
        self._compat.setdefault(provider_b, set()).add(provider_a)

    def are_compatible(self, provider_a: str, provider_b: str) -> bool:
        return provider_b in self._compat.get(provider_a, set())

    def get_compatible(self, provider: str) -> list[str]:
        return list(self._compat.get(provider, set()))
