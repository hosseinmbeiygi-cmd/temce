from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Option(BaseEntity):
    name: str
    symbol: str = ""
    underlying_symbol: str = ""
    underlying_id: str = ""
    option_type: str = ""
    strike_price: float = 0.0
    expiration_date: date | None = None
    contract_size: int = 1000
    currency: str = "IRR"
    style: str = "european"
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        symbol: str = "",
        underlying_symbol: str = "",
        underlying_id: str = "",
        option_type: str = "",
        strike_price: float = 0.0,
        expiration_date: date | None = None,
        contract_size: int = 1000,
        currency: str = "IRR",
        style: str = "european",
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.symbol = symbol
        self.underlying_symbol = underlying_symbol
        self.underlying_id = underlying_id
        self.option_type = option_type
        self.strike_price = strike_price
        self.expiration_date = expiration_date
        self.contract_size = contract_size
        self.currency = currency
        self.style = style
        self.is_active = is_active
        self.extra = extra or {}

    @property
    def is_call(self) -> bool:
        return self.option_type.lower() == "call"

    @property
    def is_put(self) -> bool:
        return self.option_type.lower() == "put"

    @property
    def days_to_expiry(self) -> int:
        if self.expiration_date is None:
            return 0
        return (self.expiration_date - date.today()).days

    @property
    def is_expired(self) -> bool:
        if self.expiration_date is None:
            return False
        return date.today() >= self.expiration_date


@dataclass
class OptionContract(BaseEntity):
    option_id: str
    contract_code: str = ""
    price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    open_interest: int = 0
    implied_volatility: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    date: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        option_id: str,
        contract_code: str = "",
        price: float = 0.0,
        bid: float = 0.0,
        ask: float = 0.0,
        volume: int = 0,
        open_interest: int = 0,
        implied_volatility: float = 0.0,
        delta: float = 0.0,
        gamma: float = 0.0,
        theta: float = 0.0,
        vega: float = 0.0,
        rho: float = 0.0,
        date: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.option_id = option_id
        self.contract_code = contract_code
        self.price = price
        self.bid = bid
        self.ask = ask
        self.volume = volume
        self.open_interest = open_interest
        self.implied_volatility = implied_volatility
        self.delta = delta
        self.gamma = gamma
        self.theta = theta
        self.vega = vega
        self.rho = rho
        self.date = date
        self.extra = extra or {}


@dataclass
class OptionTrade(BaseEntity):
    option_id: str
    side: str
    quantity: int = 0
    price: float = 0.0
    premium: float = 0.0
    date: str = ""
    time: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        option_id: str,
        side: str,
        quantity: int = 0,
        price: float = 0.0,
        premium: float = 0.0,
        date: str = "",
        time: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.option_id = option_id
        self.side = side
        self.quantity = quantity
        self.price = price
        self.premium = premium
        self.date = date
        self.time = time
        self.extra = extra or {}
