from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class PortfolioPerformance(BaseEntity):
    portfolio_id: str
    date: str = ""
    total_value: float = 0.0
    cash: float = 0.0
    invested: float = 0.0
    daily_pnl: float = 0.0
    daily_return_pct: float = 0.0
    cumulative_pnl: float = 0.0
    cumulative_return_pct: float = 0.0
    drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    volatility: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        portfolio_id: str,
        date: str = "",
        total_value: float = 0.0,
        cash: float = 0.0,
        invested: float = 0.0,
        daily_pnl: float = 0.0,
        daily_return_pct: float = 0.0,
        cumulative_pnl: float = 0.0,
        cumulative_return_pct: float = 0.0,
        drawdown: float = 0.0,
        sharpe_ratio: float = 0.0,
        volatility: float = 0.0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.portfolio_id = portfolio_id
        self.date = date
        self.total_value = total_value
        self.cash = cash
        self.invested = invested
        self.daily_pnl = daily_pnl
        self.daily_return_pct = daily_return_pct
        self.cumulative_pnl = cumulative_pnl
        self.cumulative_return_pct = cumulative_return_pct
        self.drawdown = drawdown
        self.sharpe_ratio = sharpe_ratio
        self.volatility = volatility
        self.extra = extra or {}
