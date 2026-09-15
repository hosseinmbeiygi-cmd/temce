from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import OrderSide


@dataclass
class OrderBookEntry(BaseEntity):
    instrument_id: str
    side: OrderSide
    price: float = 0.0
    volume: int = 0
    order_count: int = 0
    symbol: str = ""
    time: str = ""
    date: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        side: OrderSide,
        price: float = 0.0,
        volume: int = 0,
        order_count: int = 0,
        symbol: str = "",
        time: str = "",
        date: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.side = side
        self.price = price
        self.volume = volume
        self.order_count = order_count
        self.symbol = symbol
        self.time = time
        self.date = date
        self.extra = extra or {}

    @property
    def value(self) -> float:
        return self.price * self.volume


@dataclass
class OrderBookSnapshot(BaseEntity):
    instrument_id: str
    symbol: str = ""
    bids: list[dict[str, Any]] = field(default_factory=list)
    asks: list[dict[str, Any]] = field(default_factory=list)
    time: str = ""
    date: str = ""
    total_bid_volume: int = 0
    total_ask_volume: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        symbol: str = "",
        bids: list[dict[str, Any]] | None = None,
        asks: list[dict[str, Any]] | None = None,
        time: str = "",
        date: str = "",
        total_bid_volume: int = 0,
        total_ask_volume: int = 0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.bids = bids or []
        self.asks = asks or []
        self.time = time
        self.date = date
        self.total_bid_volume = total_bid_volume
        self.total_ask_volume = total_ask_volume
        self.extra = extra or {}

    @property
    def spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.asks[0].get("price", 0) - self.bids[0].get("price", 0)

    @property
    def mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.asks[0].get("price", 0) + self.bids[0].get("price", 0)) / 2.0
