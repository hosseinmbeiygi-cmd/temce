from __future__ import annotations

from dataclasses import dataclass

from domain.common.events import DomainEvent


@dataclass
class QuoteUpdated(DomainEvent):
    instrument_id: str = ""
    symbol: str = ""
    price: float = 0.0
    volume: int = 0


@dataclass
class QuoteThresholdBreached(DomainEvent):
    instrument_id: str = ""
    symbol: str = ""
    field: str = ""
    value: float = 0.0
    threshold: float = 0.0
