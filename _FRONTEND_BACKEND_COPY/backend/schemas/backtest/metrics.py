from __future__ import annotations

from pydantic import BaseModel


class EquityCurvePoint(BaseModel):
    date: str = ""
    value: float = 0.0
    drawdown_pct: float = 0.0


class TradeRecord(BaseModel):
    entry_date: str = ""
    exit_date: str = ""
    symbol: str = ""
    direction: str = "long"
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    gross_profit: float = 0.0
    net_profit: float = 0.0
    return_pct: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    exit_reason: str = ""


class BacktestMetrics(BaseModel):
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    volatility_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_days: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    avg_trade_duration_days: float = 0.0
    expectancy: float = 0.0
