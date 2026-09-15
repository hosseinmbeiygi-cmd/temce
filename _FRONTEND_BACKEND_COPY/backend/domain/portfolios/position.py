from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Position(BaseEntity):
    portfolio_id: str
    instrument_id: str
    symbol: str = ""
    quantity: int = 0
    avg_price: float = 0.0
    current_price: float = 0.0
    cost_basis: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    return_pct: float = 0.0
    weight_pct: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        portfolio_id: str,
        instrument_id: str,
        symbol: str = "",
        quantity: int = 0,
        avg_price: float = 0.0,
        current_price: float = 0.0,
        cost_basis: float = 0.0,
        market_value: float = 0.0,
        unrealized_pnl: float = 0.0,
        realized_pnl: float = 0.0,
        return_pct: float = 0.0,
        weight_pct: float = 0.0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.portfolio_id = portfolio_id
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.quantity = quantity
        self.avg_price = avg_price
        self.current_price = current_price
        self.cost_basis = cost_basis
        self.market_value = market_value
        self.unrealized_pnl = unrealized_pnl
        self.realized_pnl = realized_pnl
        self.return_pct = return_pct
        self.weight_pct = weight_pct
        self.extra = extra or {}
