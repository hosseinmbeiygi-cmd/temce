from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class QuoteSnapshot(BaseEntity):
    instrument_id: str
    symbol: str = ""
    price_open: float = 0.0
    price_close: float = 0.0
    price_high: float = 0.0
    price_low: float = 0.0
    price_last: float = 0.0
    price_change: float = 0.0
    price_change_pct: float = 0.0
    price_yesterday: float = 0.0
    volume: int = 0
    value: float = 0.0
    trade_count: int = 0
    market_status: str = ""
    date: str = ""
    time: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        price_open: float = 0.0,
        price_close: float = 0.0,
        price_high: float = 0.0,
        price_low: float = 0.0,
        price_last: float = 0.0,
        price_change: float = 0.0,
        price_change_pct: float = 0.0,
        price_yesterday: float = 0.0,
        volume: int = 0,
        value: float = 0.0,
        trade_count: int = 0,
        market_status: str = "",
        date: str = "",
        time: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.price_open = price_open
        self.price_close = price_close
        self.price_high = price_high
        self.price_low = price_low
        self.price_last = price_last
        self.price_change = price_change
        self.price_change_pct = price_change_pct
        self.price_yesterday = price_yesterday
        self.volume = volume
        self.value = value
        self.trade_count = trade_count
        self.market_status = market_status
        self.date = date
        self.time = time
        self.extra = extra or {}


@dataclass
class QuoteSummary(BaseEntity):
    instrument_id: str
    symbol: str = ""
    avg_price: float = 0.0
    median_price: float = 0.0
    std_dev: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    total_volume: int = 0
    total_value: float = 0.0
    vwap: float = 0.0
    date: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        avg_price: float = 0.0,
        median_price: float = 0.0,
        std_dev: float = 0.0,
        min_price: float = 0.0,
        max_price: float = 0.0,
        total_volume: int = 0,
        total_value: float = 0.0,
        vwap: float = 0.0,
        date: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.avg_price = avg_price
        self.median_price = median_price
        self.std_dev = std_dev
        self.min_price = min_price
        self.max_price = max_price
        self.total_volume = total_volume
        self.total_value = total_value
        self.vwap = vwap
        self.date = date
        self.extra = extra or {}
