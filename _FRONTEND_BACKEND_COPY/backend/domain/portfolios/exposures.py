from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class PortfolioExposure(BaseEntity):
    portfolio_id: str
    instrument_id: str
    symbol: str = ""
    exposure_type: str = "long"
    quantity: int = 0
    market_value: float = 0.0
    weight_pct: float = 0.0
    sector: str = ""
    asset_class: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        portfolio_id: str,
        instrument_id: str,
        symbol: str = "",
        exposure_type: str = "long",
        quantity: int = 0,
        market_value: float = 0.0,
        weight_pct: float = 0.0,
        sector: str = "",
        asset_class: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.portfolio_id = portfolio_id
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.exposure_type = exposure_type
        self.quantity = quantity
        self.market_value = market_value
        self.weight_pct = weight_pct
        self.sector = sector
        self.asset_class = asset_class
        self.extra = extra or {}
