from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class TradeReport(BaseEntity):
    instrument_id: str
    symbol: str = ""
    total_volume: int = 0
    total_value: float = 0.0
    total_trades: int = 0
    avg_price: float = 0.0
    vwap: float = 0.0
    max_price: float = 0.0
    min_price: float = 0.0
    first_price: float = 0.0
    last_price: float = 0.0
    price_change: float = 0.0
    price_change_pct: float = 0.0
    date: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        total_volume: int = 0,
        total_value: float = 0.0,
        total_trades: int = 0,
        avg_price: float = 0.0,
        vwap: float = 0.0,
        max_price: float = 0.0,
        min_price: float = 0.0,
        first_price: float = 0.0,
        last_price: float = 0.0,
        price_change: float = 0.0,
        price_change_pct: float = 0.0,
        date: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.total_volume = total_volume
        self.total_value = total_value
        self.total_trades = total_trades
        self.avg_price = avg_price
        self.vwap = vwap
        self.max_price = max_price
        self.min_price = min_price
        self.first_price = first_price
        self.last_price = last_price
        self.price_change = price_change
        self.price_change_pct = price_change_pct
        self.date = date
        self.extra = extra or {}
