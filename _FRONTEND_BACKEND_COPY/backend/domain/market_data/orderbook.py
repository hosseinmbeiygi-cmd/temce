from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class OrderBookLevel:
    price: float
    volume: int
    count: int = 0
    side: str = ""

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("price must be positive")

    @property
    def value(self) -> float:
        return self.price * self.volume


@dataclass
class OrderBook(BaseEntity):
    instrument_id: str
    symbol: str = ""
    time: str = ""
    date: str = ""
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    data_source: str = "tsetmc"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        time: str = "",
        date: str = "",
        bids: list[OrderBookLevel] | None = None,
        asks: list[OrderBookLevel] | None = None,
        data_source: str = "tsetmc",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.time = time
        self.date = date
        self.bids = bids or []
        self.asks = asks or []
        self.data_source = data_source
        self.extra = extra or {}

    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0.0

    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid if self.best_bid > 0 and self.best_ask > 0 else 0.0

    @property
    def total_bid_volume(self) -> int:
        return sum(b.volume for b in self.bids)

    @property
    def total_ask_volume(self) -> int:
        return sum(a.volume for a in self.asks)

    @property
    def imbalance_ratio(self) -> float:
        total = self.total_bid_volume + self.total_ask_volume
        if total == 0:
            return 0.0
        return (self.total_bid_volume - self.total_ask_volume) / total
