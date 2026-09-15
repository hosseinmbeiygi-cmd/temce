from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Analysis(BaseEntity):
    instrument_id: str
    analysis_type: str
    symbol: str = ""
    value: float = 0.0
    score: float = 0.0
    date: str = ""
    timeframe: str = "1d"
    parameters: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        analysis_type: str,
        symbol: str = "",
        value: float = 0.0,
        score: float = 0.0,
        date: str = "",
        timeframe: str = "1d",
        parameters: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.analysis_type = analysis_type
        self.symbol = symbol
        self.value = value
        self.score = score
        self.date = date
        self.timeframe = timeframe
        self.parameters = parameters or {}
        self.extra = extra or {}
