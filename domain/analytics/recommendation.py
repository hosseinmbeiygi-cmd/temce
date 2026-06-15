from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import RecommendationAction


@dataclass
class Recommendation(BaseEntity):
    instrument_id: str
    action: RecommendationAction
    symbol: str = ""
    target_price: float | None = None
    current_price: float = 0.0
    potential_return_pct: float = 0.0
    confidence: float = 0.0
    horizon: str = "medium_term"
    source: str = ""
    analyst: str = ""
    rationale: str = ""
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        action: RecommendationAction,
        symbol: str = "",
        target_price: float | None = None,
        current_price: float = 0.0,
        potential_return_pct: float = 0.0,
        confidence: float = 0.0,
        horizon: str = "medium_term",
        source: str = "",
        analyst: str = "",
        rationale: str = "",
        tags: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.action = action
        self.symbol = symbol
        self.target_price = target_price
        self.current_price = current_price
        self.potential_return_pct = potential_return_pct
        self.confidence = confidence
        self.horizon = horizon
        self.source = source
        self.analyst = analyst
        self.rationale = rationale
        self.tags = tags or []
        self.extra = extra or {}
