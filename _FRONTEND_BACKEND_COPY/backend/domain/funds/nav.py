from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class FundNAV(BaseEntity):
    fund_id: str
    nav_date: date | None = None
    nav: float = 0.0
    unit_price: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    total_units: int = 0
    daily_return_pct: float = 0.0
    cumulative_return_pct: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        fund_id: str,
        nav_date: date | None = None,
        nav: float = 0.0,
        unit_price: float = 0.0,
        total_assets: float = 0.0,
        total_liabilities: float = 0.0,
        total_units: int = 0,
        daily_return_pct: float = 0.0,
        cumulative_return_pct: float = 0.0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.fund_id = fund_id
        self.nav_date = nav_date
        self.nav = nav
        self.unit_price = unit_price
        self.total_assets = total_assets
        self.total_liabilities = total_liabilities
        self.total_units = total_units
        self.daily_return_pct = daily_return_pct
        self.cumulative_return_pct = cumulative_return_pct
        self.extra = extra or {}
