from __future__ import annotations

from dataclasses import dataclass

from domain.common.events import DomainEvent


@dataclass
class OrderBookEvent(DomainEvent):
    instrument_id: str = ""
    symbol: str = ""
    event_type: str = ""
    price: float = 0.0
    volume: int = 0
    side: str = ""


@dataclass
class OrderBookUpdated(DomainEvent):
    instrument_id: str = ""
    symbol: str = ""


@dataclass
class OrderBookLevelChanged(DomainEvent):
    instrument_id: str = ""
    side: str = ""
    price: float = 0.0
    old_volume: int = 0
    new_volume: int = 0
