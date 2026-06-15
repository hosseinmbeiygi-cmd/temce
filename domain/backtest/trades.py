from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity
from domain.common.enum_types import OrderSide


@dataclass
class BacktestTrade(BaseEntity):
    backtest_run_id: str
    instrument_id: str
    side: OrderSide
    symbol: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    entry_date: str = ""
    exit_date: str = ""
    pnl: float = 0.0
    return_pct: float = 0.0
    holding_period: int = 0
    exit_reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        backtest_run_id: str,
        instrument_id: str,
        side: OrderSide,
        symbol: str = "",
        entry_price: float = 0.0,
        exit_price: float = 0.0,
        quantity: int = 0,
        entry_date: str = "",
        exit_date: str = "",
        pnl: float = 0.0,
        return_pct: float = 0.0,
        holding_period: int = 0,
        exit_reason: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.backtest_run_id = backtest_run_id
        self.instrument_id = instrument_id
        self.side = side
        self.symbol = symbol
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.quantity = quantity
        self.entry_date = entry_date
        self.exit_date = exit_date
        self.pnl = pnl
        self.return_pct = return_pct
        self.holding_period = holding_period
        self.exit_reason = exit_reason
        self.extra = extra or {}

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0

    @property
    def is_loser(self) -> bool:
        return self.pnl < 0
