from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class PositionSummary(BaseEntity):
    portfolio_id: str
    instrument_id: str
    symbol: str = ""
    long_quantity: int = 0
    short_quantity: int = 0
    net_quantity: int = 0
    avg_long_price: float = 0.0
    avg_short_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    market_value: float = 0.0
    cost_basis: float = 0.0
    return_pct: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        portfolio_id: str,
        instrument_id: str,
        symbol: str = "",
        long_quantity: int = 0,
        short_quantity: int = 0,
        net_quantity: int = 0,
        avg_long_price: float = 0.0,
        avg_short_price: float = 0.0,
        current_price: float = 0.0,
        unrealized_pnl: float = 0.0,
        realized_pnl: float = 0.0,
        market_value: float = 0.0,
        cost_basis: float = 0.0,
        return_pct: float = 0.0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.portfolio_id = portfolio_id
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.long_quantity = long_quantity
        self.short_quantity = short_quantity
        self.net_quantity = net_quantity
        self.avg_long_price = avg_long_price
        self.avg_short_price = avg_short_price
        self.current_price = current_price
        self.unrealized_pnl = unrealized_pnl
        self.realized_pnl = realized_pnl
        self.market_value = market_value
        self.cost_basis = cost_basis
        self.return_pct = return_pct
        self.extra = extra or {}

    @property
    def is_long(self) -> bool:
        return self.net_quantity > 0

    @property
    def is_short(self) -> bool:
        return self.net_quantity < 0

    @property
    def is_flat(self) -> bool:
        return self.net_quantity == 0
