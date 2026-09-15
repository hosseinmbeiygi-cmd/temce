from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import RecommendationAction


@dataclass
class RecommendationLog(BaseEntity):
    instrument_id: str
    action: RecommendationAction
    symbol: str = ""
    previous_action: str = ""
    score: float = 0.0
    confidence: float = 0.0
    source: str = ""
    analyst: str = ""
    rationale: str = ""
    date: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        action: RecommendationAction,
        symbol: str = "",
        previous_action: str = "",
        score: float = 0.0,
        confidence: float = 0.0,
        source: str = "",
        analyst: str = "",
        rationale: str = "",
        date: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.action = action
        self.symbol = symbol
        self.previous_action = previous_action
        self.score = score
        self.confidence = confidence
        self.source = source
        self.analyst = analyst
        self.rationale = rationale
        self.date = date
        self.extra = extra or {}

    @property
    def is_upgrade(self) -> bool:
        upgrades = {"sell": "hold", "hold": "buy", "reduce": "accumulate"}
        return upgrades.get(self.previous_action, "") == self.action.value

    @property
    def is_downgrade(self) -> bool:
        downgrades = {"buy": "hold", "hold": "sell", "accumulate": "reduce"}
        return downgrades.get(self.previous_action, "") == self.action.value
