from __future__ import annotations

from core.logging import get_logger
from providers.capabilities.matrix import CapabilityMatrix

logger = get_logger(__name__)


class ProviderSelector:
    def __init__(self, matrix: CapabilityMatrix | None = None) -> None:
        self.matrix = matrix or CapabilityMatrix()

    def select(self, required_features: list[str], preferred_provider: str | None = None) -> str | None:
        if preferred_provider and all(self.matrix.has_capability(preferred_provider, f) for f in required_features):
            return preferred_provider
        for feature in required_features:
            providers = self.matrix.find_providers(feature)
            if not providers:
                logger.warning("No provider found for feature: %s", feature)
                return None
        candidates: set[str] | None = None
        for feature in required_features:
            providers = set(self.matrix.find_providers(feature))
            if candidates is None:
                candidates = providers
            else:
                candidates &= providers
        if candidates:
            return sorted(candidates)[0]
        logger.warning("No single provider supports all: %s", required_features)
        return None

    def rank(self, required_features: list[str]) -> list[tuple[str, int]]:
        scores: dict[str, int] = {}
        for feature in required_features:
            for provider in self.matrix.find_providers(feature):
                scores[provider] = scores.get(provider, 0) + 1
        return sorted(scores.items(), key=lambda x: -x[1])
