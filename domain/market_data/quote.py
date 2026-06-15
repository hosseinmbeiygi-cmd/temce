from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Quote(BaseEntity):
    instrument_id: str
    symbol: str = ""
    price_close: float = 0.0
    price_open: float = 0.0
    price_high: float = 0.0
    price_low: float = 0.0
    price_last: float = 0.0
    price_change: float = 0.0
    price_change_pct: float = 0.0
    volume: int = 0
    value: float = 0.0
    trade_count: int = 0
    price_yesterday: float = 0.0
    price_first: float = 0.0
    price_max: float = 0.0
    price_min: float = 0.0
    ask_price: float = 0.0
    ask_volume: int = 0
    bid_price: float = 0.0
    bid_volume: int = 0
    market_status: str = ""
    time: str = ""
    date: str = ""
    timeframe: str = "1d"
    data_source: str = "tsetmc"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        price_close: float = 0.0,
        price_open: float = 0.0,
        price_high: float = 0.0,
        price_low: float = 0.0,
        price_last: float = 0.0,
        price_change: float = 0.0,
        price_change_pct: float = 0.0,
        volume: int = 0,
        value: float = 0.0,
        trade_count: int = 0,
        price_yesterday: float = 0.0,
        price_first: float = 0.0,
        price_max: float = 0.0,
        price_min: float = 0.0,
        ask_price: float = 0.0,
        ask_volume: int = 0,
        bid_price: float = 0.0,
        bid_volume: int = 0,
        market_status: str = "",
        time: str = "",
        date: str = "",
        timeframe: str = "1d",
        data_source: str = "tsetmc",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.price_close = price_close
        self.price_open = price_open
        self.price_high = price_high
        self.price_low = price_low
        self.price_last = price_last
        self.price_change = price_change
        self.price_change_pct = price_change_pct
        self.volume = volume
        self.value = value
        self.trade_count = trade_count
        self.price_yesterday = price_yesterday
        self.price_first = price_first
        self.price_max = price_max
        self.price_min = price_min
        self.ask_price = ask_price
        self.ask_volume = ask_volume
        self.bid_price = bid_price
        self.bid_volume = bid_volume
        self.market_status = market_status
        self.time = time
        self.date = date
        self.timeframe = timeframe
        self.data_source = data_source
        self.extra = extra or {}

    @property
    def spread(self) -> float:
        return self.ask_price - self.bid_price if self.ask_price > 0 and self.bid_price > 0 else 0.0

    @property
    def spread_bps(self) -> float:
        if self.bid_price > 0 and self.spread > 0:
            return (self.spread / self.bid_price) * 10000
        return 0.0

    @property
    def turnover_ratio(self) -> float:
        return 0.0

    def is_positive(self) -> bool:
        return self.price_change > 0

    def is_negative(self) -> bool:
        return self.price_change < 0

    def range_pct(self) -> float:
        if self.price_close == 0:
            return 0.0
        if self.price_yesterday > 0:
            return ((self.price_close - self.price_yesterday) / self.price_yesterday) * 100
        return 0.0
