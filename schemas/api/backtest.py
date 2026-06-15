from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    name: str = "Backtest"
    symbols: list[str]
    strategy_type: str = "moving_average_crossover"
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    start_date: date
    end_date: date
    initial_capital: float = 1_000_000_000
    commission_pct: float = 0.0035
    slippage_bps: float = 10.0
    timeframe: str = "1d"


class BacktestResponse(BaseModel):
    id: str
    name: str
    status: str = "queued"
    progress_pct: float = 0.0
    message: str = "Backtest queued for execution"


class BacktestResultResponse(BaseModel):
    id: str
    name: str
    status: str = "completed"
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    initial_capital: float = 0.0
    final_value: float = 0.0
    equity_curve: list[dict[str, Any]] = Field(default_factory=list)
    trades: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    completed_at: str = ""
