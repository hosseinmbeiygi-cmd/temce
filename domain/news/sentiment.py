from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class SentimentAnalysis(BaseEntity):
    news_id: str
    score: float = 0.0
    label: str = "neutral"
    confidence: float = 0.0
    model: str = ""
    aspects: dict[str, float] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        news_id: str,
        score: float = 0.0,
        label: str = "neutral",
        confidence: float = 0.0,
        model: str = "",
        aspects: dict[str, float] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.news_id = news_id
        self.score = score
        self.label = label
        self.confidence = confidence
        self.model = model
        self.aspects = aspects or {}
        self.extra = extra or {}

    @property
    def is_positive(self) -> bool:
        return self.score > 0.1

    @property
    def is_negative(self) -> bool:
        return self.score < -0.1

    @property
    def is_neutral(self) -> bool:
        return -0.1 <= self.score <= 0.1
