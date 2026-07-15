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
    data_source: str = "auto"  # auto, historical, quotes, intraday
    # Position sizing
    sizing_method: str = "fixed"  # fixed, percent, kelly, risk_based
    sizing_value: float = 1000.0
    # Risk management
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    # Benchmark
    benchmark_symbol: str | None = None
    # Portfolio
    allocation_method: str = "equal"  # equal, weighted
    target_weights: dict[str, float] | None = None
    rebalance_frequency_days: int | None = None


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
    # Benchmark metrics
    alpha: float | None = None
    beta: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None
    # Data quality
    data_quality: dict[str, Any] | None = None
    # Data source warning
    data_source_warning: str | None = None
