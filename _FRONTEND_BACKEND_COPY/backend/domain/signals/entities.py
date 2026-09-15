from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import SignalType


@dataclass
class SignalEvent(BaseEntity):
    instrument_id: str
    signal_type: SignalType
    symbol: str = ""
    score: float = 0.0
    confidence: float = 0.0
    strength: float = 0.0
    source: str = ""
    strategy: str = ""
    timeframe: str = "1d"
    date: str = ""
    time: str = ""
    description: str = ""
    reasons: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        signal_type: SignalType,
        symbol: str = "",
        score: float = 0.0,
        confidence: float = 0.0,
        strength: float = 0.0,
        source: str = "",
        strategy: str = "",
        timeframe: str = "1d",
        date: str = "",
        time: str = "",
        description: str = "",
        reasons: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.signal_type = signal_type
        self.symbol = symbol
        self.score = score
        self.confidence = confidence
        self.strength = strength
        self.source = source
        self.strategy = strategy
        self.timeframe = timeframe
        self.date = date
        self.time = time
        self.description = description
        self.reasons = reasons or []
        self.extra = extra or {}

    @property
    def is_bullish(self) -> bool:
        return self.signal_type in (SignalType.BULLISH, SignalType.STRONG_BUY)

    @property
    def is_bearish(self) -> bool:
        return self.signal_type in (SignalType.BEARISH, SignalType.STRONG_SELL)

    @property
    def is_strong(self) -> bool:
        return self.strength >= 0.8

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.7


@dataclass
class SignalLog(BaseEntity):
    signal_id: str
    action: str = ""
    previous_score: float = 0.0
    new_score: float = 0.0
    change_reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        signal_id: str,
        action: str = "",
        previous_score: float = 0.0,
        new_score: float = 0.0,
        change_reason: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.signal_id = signal_id
        self.action = action
        self.previous_score = previous_score
        self.new_score = new_score
        self.change_reason = change_reason
        self.extra = extra or {}

    @property
    def score_change(self) -> float:
        return self.new_score - self.previous_score
