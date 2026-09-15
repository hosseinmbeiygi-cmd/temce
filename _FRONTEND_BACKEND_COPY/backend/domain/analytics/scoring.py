from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Scoring(BaseEntity):
    instrument_id: str
    symbol: str = ""
    overall_score: float = 0.0
    category: str = ""
    components: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    normalized: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        overall_score: float = 0.0,
        category: str = "",
        components: dict[str, float] | None = None,
        weights: dict[str, float] | None = None,
        normalized: bool = False,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.overall_score = overall_score
        self.category = category
        self.components = components or {}
        self.weights = weights or {}
        self.normalized = normalized
        self.extra = extra or {}

    def compute_weighted_score(self) -> float:
        total = 0.0
        weight_sum = 0.0
        for name, score in self.components.items():
            w = self.weights.get(name, 1.0)
            total += score * w
            weight_sum += w
        return total / weight_sum if weight_sum > 0 else 0.0

    def add_component(self, name: str, score: float, weight: float = 1.0) -> None:
        self.components[name] = score
        self.weights[name] = weight
        self.overall_score = self.compute_weighted_score()
        self.mark_updated()
