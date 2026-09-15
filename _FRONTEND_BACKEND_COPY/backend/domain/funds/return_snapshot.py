from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class FundReturnSnapshot(BaseEntity):
    fund_id: str
    period: str = ""
    return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    benchmark_return_pct: float = 0.0
    excess_return_pct: float = 0.0
    volatility_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        fund_id: str,
        period: str = "",
        return_pct: float = 0.0,
        annualized_return_pct: float = 0.0,
        benchmark_return_pct: float = 0.0,
        excess_return_pct: float = 0.0,
        volatility_pct: float = 0.0,
        sharpe_ratio: float = 0.0,
        max_drawdown_pct: float = 0.0,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.fund_id = fund_id
        self.period = period
        self.return_pct = return_pct
        self.annualized_return_pct = annualized_return_pct
        self.benchmark_return_pct = benchmark_return_pct
        self.excess_return_pct = excess_return_pct
        self.volatility_pct = volatility_pct
        self.sharpe_ratio = sharpe_ratio
        self.max_drawdown_pct = max_drawdown_pct
        self.extra = extra or {}
