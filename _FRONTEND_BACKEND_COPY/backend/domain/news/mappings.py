from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class NewsSymbolMapping(BaseEntity):
    news_id: str
    instrument_id: str
    symbol: str = ""
    relevance_score: float = 1.0
    mapping_type: str = "explicit"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        news_id: str,
        instrument_id: str,
        symbol: str = "",
        relevance_score: float = 1.0,
        mapping_type: str = "explicit",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.news_id = news_id
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.relevance_score = relevance_score
        self.mapping_type = mapping_type
        self.extra = extra or {}
