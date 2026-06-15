from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BacktestConfigSchema(BaseModel):
    strategy_name: str
    instrument_ids: list[str] = []
    capital: float = 1_000_000_000
    start_date: str = ""
    end_date: str = ""
    commission_pct: float = 0.0035
    slippage_bps: float = 10.0


class BacktestResultSchema(BaseModel):
    strategy_name: str = ""
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    metrics: dict[str, float] = {}
    completed_at: datetime | None = None
