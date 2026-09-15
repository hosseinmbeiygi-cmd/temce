from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ProviderCapabilities:
    def __init__(self, name: str, features: list[str] | None = None) -> None:
        self.name = name
        self.features: dict[str, bool] = dict.fromkeys(features or [], True)

    def supports(self, feature: str) -> bool:
        return self.features.get(feature, False)

    def enable(self, feature: str) -> None:
        self.features[feature] = True

    def disable(self, feature: str) -> None:
        self.features[feature] = False

    def list_features(self) -> list[str]:
        return [k for k, v in self.features.items() if v]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "features": dict(self.features)}
