from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AlphaSignal:
    """A single alpha signal."""
    alpha_id: str
    name: str
    formula: str
    values: list[float] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


class AlphaPool:
    """Manages a pool of alpha signals with generation, storage, and retrieval."""

    def __init__(self, max_alphas: int = 5000) -> None:
        self.max_alphas = max_alphas
        self._alphas: dict[str, AlphaSignal] = {}
        self._feature_names: set[str] = set()

    def add_alpha(self, alpha: AlphaSignal) -> None:
        if len(self._alphas) >= self.max_alphas:
            oldest = min(self._alphas.keys(), key=lambda k: self._alphas[k].created_at)
            del self._alphas[oldest]
        self._alphas[alpha.alpha_id] = alpha

    def get_alpha(self, alpha_id: str) -> AlphaSignal | None:
        return self._alphas.get(alpha_id)

    def remove_alpha(self, alpha_id: str) -> None:
        self._alphas.pop(alpha_id, None)

    def clear(self) -> None:
        self._alphas.clear()

    @property
    def alpha_ids(self) -> list[str]:
        return list(self._alphas.keys())

    @property
    def count(self) -> int:
        return len(self._alphas)

    def register_features(self, feature_names: list[str]) -> None:
        self._feature_names.update(feature_names)

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    def apply_all(self, features: dict[str, float], evaluator_fn: Callable[[str, AlphaSignal, dict[str, float]], float]) -> dict[str, float]:
        """Apply all alphas to given features using evaluator function."""
        results: dict[str, float] = {}
        for alpha_id, alpha in self._alphas.items():
            try:
                value = evaluator_fn(alpha_id, alpha, features)
                results[alpha_id] = value
            except Exception as e:
                logger.warning("Alpha %s failed evaluation: %s", alpha_id, e)
                continue
        return results
