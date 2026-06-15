from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Commodity(BaseEntity):
    name: str
    symbol: str = ""
    category: str = ""
    sub_category: str = ""
    unit: str = ""
    currency: str = "USD"
    exchange: str = ""
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        symbol: str = "",
        category: str = "",
        sub_category: str = "",
        unit: str = "",
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
        self.category = category
        self.sub_category = sub_category
        self.unit = unit
        self.currency = currency
        self.exchange = exchange
        self.is_active = is_active
        self.extra = extra or {}


@dataclass
class CommodityContract(BaseEntity):
    commodity_id: str
    contract_code: str = ""
    delivery_month: str = ""
    delivery_year: int = 0
    price: float = 0.0
    volume: int = 0
    currency: str = "USD"
    status: str = "active"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        commodity_id: str,
        contract_code: str = "",
        delivery_month: str = "",
        delivery_year: int = 0,
        price: float = 0.0,
        volume: int = 0,
        currency: str = "USD",
        status: str = "active",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.commodity_id = commodity_id
        self.contract_code = contract_code
        self.delivery_month = delivery_month
        self.delivery_year = delivery_year
        self.price = price
        self.volume = volume
        self.currency = currency
        self.status = status
        self.extra = extra or {}
