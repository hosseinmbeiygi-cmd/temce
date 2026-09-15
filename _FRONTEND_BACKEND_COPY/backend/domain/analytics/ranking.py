from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Ranking(BaseEntity):
    instrument_id: str
    symbol: str = ""
    rank: int = 0
    score: float = 0.0
    category: str = ""
    total_items: int = 0
    percentile: float = 0.0
    factors: dict[str, float] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        rank: int = 0,
        score: float = 0.0,
        category: str = "",
        total_items: int = 0,
        percentile: float = 0.0,
        factors: dict[str, float] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.rank = rank
        self.score = score
        self.category = category
        self.total_items = total_items
        self.percentile = percentile
        self.factors = factors or {}
        self.extra = extra or {}

    @property
    def is_top_quartile(self) -> bool:
        return self.percentile >= 75.0

    @property
    def is_bottom_quartile(self) -> bool:
        return self.percentile <= 25.0
