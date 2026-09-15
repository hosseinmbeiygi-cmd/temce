from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Fund(BaseEntity):
    name: str
    symbol: str = ""
    isin: str = ""
    fund_type: str = ""
    manager: str = ""
    custodian: str = ""
    currency: str = "IRR"
    nav: float = 0.0
    total_units: int = 0
    unit_price: float = 0.0
    status: str = "active"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        symbol: str = "",
        isin: str = "",
        fund_type: str = "",
        manager: str = "",
        custodian: str = "",
        currency: str = "IRR",
        nav: float = 0.0,
        total_units: int = 0,
        unit_price: float = 0.0,
        status: str = "active",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.symbol = symbol
        self.isin = isin
        self.fund_type = fund_type
        self.manager = manager
        self.custodian = custodian
        self.currency = currency
        self.nav = nav
        self.total_units = total_units
        self.unit_price = unit_price
        self.status = status
        self.extra = extra or {}


@dataclass
class FundHolding(BaseEntity):
    fund_id: str
    instrument_id: str
    symbol: str = ""
    quantity: int = 0
    market_value: float = 0.0
    weight_pct: float = 0.0
    asset_type: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        fund_id: str,
        instrument_id: str,
        symbol: str = "",
        quantity: int = 0,
        market_value: float = 0.0,
        weight_pct: float = 0.0,
        asset_type: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.fund_id = fund_id
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.quantity = quantity
        self.market_value = market_value
        self.weight_pct = weight_pct
        self.asset_type = asset_type
        self.extra = extra or {}
