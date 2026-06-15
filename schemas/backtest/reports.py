from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.backtest.metrics import BacktestMetrics, EquityCurvePoint, TradeRecord


class BacktestReportSummary(BaseModel):
    name: str = ""
    strategy_type: str = ""
    symbol: str = ""
    timeframe: str = "1d"
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 0.0
    final_value: float = 0.0
    metrics: BacktestMetrics = Field(default_factory=BacktestMetrics)


class BacktestReport(BaseModel):
    id: str
    summary: BacktestReportSummary = Field(default_factory=BacktestReportSummary)
    trades: list[TradeRecord] = Field(default_factory=list)
    equity_curve: list[EquityCurvePoint] = Field(default_factory=list)
    monthly_returns: dict[str, float] = Field(default_factory=dict)
    yearly_returns: dict[str, float] = Field(default_factory=dict)
    drawdown_curve: list[EquityCurvePoint] = Field(default_factory=list)
    generated_at: str = ""
