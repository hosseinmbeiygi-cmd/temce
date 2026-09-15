from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class CurrencyPair(BaseEntity):
    base_currency: str
    quote_currency: str
    symbol: str = ""
    name: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0
    change_pct: float = 0.0
    pip_size: int = 4
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        base_currency: str,
        quote_currency: str,
        symbol: str = "",
        name: str = "",
        bid: float = 0.0,
        ask: float = 0.0,
        last: float = 0.0,
        high: float = 0.0,
        low: float = 0.0,
        volume: float = 0.0,
        change_pct: float = 0.0,
        pip_size: int = 4,
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self.symbol = symbol
        self.name = name
        self.bid = bid
        self.ask = ask
        self.last = last
        self.high = high
        self.low = low
        self.volume = volume
        self.change_pct = change_pct
        self.pip_size = pip_size
        self.is_active = is_active
        self.extra = extra or {}

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_pips(self) -> float:
        return self.spread * (10**self.pip_size)


@dataclass
class FxRate(BaseEntity):
    pair_id: str
    rate: float = 0.0
    rate_type: str = "spot"
    date: str = ""
    time: str = ""
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        pair_id: str,
        rate: float = 0.0,
        rate_type: str = "spot",
        date: str = "",
        time: str = "",
        source: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.pair_id = pair_id
        self.rate = rate
        self.rate_type = rate_type
        self.date = date
        self.time = time
        self.source = source
        self.extra = extra or {}


@dataclass
class FxTrade(BaseEntity):
    pair_id: str
    side: str
    quantity: float = 0.0
    price: float = 0.0
    value: float = 0.0
    date: str = ""
    time: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        pair_id: str,
        side: str,
        quantity: float = 0.0,
        price: float = 0.0,
        value: float = 0.0,
        date: str = "",
        time: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.pair_id = pair_id
        self.side = side
        self.quantity = quantity
        self.price = price
        self.value = value
        self.date = date
        self.time = time
        self.extra = extra or {}
