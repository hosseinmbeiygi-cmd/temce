from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Metal(BaseEntity):
    name: str
    symbol: str = ""
    metal_type: str = ""
    unit: str = "oz"
    currency: str = "USD"
    exchange: str = ""
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        symbol: str = "",
        metal_type: str = "",
        unit: str = "oz",
        currency: str = "USD",
        exchange: str = "",
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.symbol = symbol
        self.metal_type = metal_type
        self.unit = unit
        self.currency = currency
        self.exchange = exchange
        self.is_active = is_active
        self.extra = extra or {}


@dataclass
class MetalQuote(BaseEntity):
    metal_id: str
    price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    high: float = 0.0
    low: float = 0.0
    change_pct: float = 0.0
    volume: float = 0.0
    date: str = ""
    time: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        metal_id: str,
        price: float = 0.0,
        bid: float = 0.0,
        ask: float = 0.0,
        high: float = 0.0,
        low: float = 0.0,
        change_pct: float = 0.0,
        volume: float = 0.0,
        date: str = "",
        time: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.metal_id = metal_id
        self.price = price
        self.bid = bid
        self.ask = ask
        self.high = high
        self.low = low
        self.change_pct = change_pct
        self.volume = volume
        self.date = date
        self.time = time
        self.extra = extra or {}
