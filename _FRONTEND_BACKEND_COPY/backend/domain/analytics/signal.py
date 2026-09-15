from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import SignalType


@dataclass
class Signal(BaseEntity):
    instrument_id: str
    signal_type: SignalType
    score: float = 0.0
    confidence: float = 0.0
    symbol: str = ""
    source: str = ""
    strategy: str = ""
    timeframe: str = "1d"
    date: str = ""
    time: str = ""
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        signal_type: SignalType,
        score: float = 0.0,
        confidence: float = 0.0,
        symbol: str = "",
        source: str = "",
        strategy: str = "",
        timeframe: str = "1d",
        date: str = "",
        time: str = "",
        description: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.signal_type = signal_type
        self.score = score
        self.confidence = confidence
        self.symbol = symbol
        self.source = source
        self.strategy = strategy
        self.timeframe = timeframe
        self.date = date
        self.time = time
        self.description = description
        self.extra = extra or {}

    @property
    def is_bullish(self) -> bool:
        return self.signal_type in (SignalType.BULLISH, SignalType.STRONG_BUY)

    @property
    def is_bearish(self) -> bool:
        return self.signal_type in (SignalType.BEARISH, SignalType.STRONG_SELL)

    @property
    def is_strong(self) -> bool:
        return self.confidence >= 0.8

    @property
    def weighted_score(self) -> float:
        return self.score * self.confidence
