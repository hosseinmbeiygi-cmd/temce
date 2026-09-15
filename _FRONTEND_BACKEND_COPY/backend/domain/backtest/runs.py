from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class BacktestRunConfig:
    name: str
    strategy_name: str
    instrument_ids: list[str] = field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    initial_capital: float = 1000000.0
    commission_pct: float = 0.0
    slippage_pct: float = 0.0
    price_field: str = "close"
    rebalance_frequency: str = "daily"
    parameters: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
