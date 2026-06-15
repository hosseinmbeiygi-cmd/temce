from __future__ import annotations

from dataclasses import dataclass

from domain.common.events import DomainEvent


@dataclass
class TradeExecuted(DomainEvent):
    instrument_id: str = ""
    symbol: str = ""
    price: float = 0.0
    volume: int = 0
    value: float = 0.0
    side: str = ""


@dataclass
class TradeBatchProcessed(DomainEvent):
    instrument_id: str = ""
    symbol: str = ""
    trade_count: int = 0
    total_volume: int = 0
    total_value: float = 0.0
