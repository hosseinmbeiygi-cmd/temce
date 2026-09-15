from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BacktestRunCreate(BaseModel):
    name: str
    strategy_type: str
    symbols: list[str]
    start_date: str
    end_date: str
    initial_capital: float = 1_000_000_000
    commission_pct: float = 0.0035
    slippage_bps: float = 10.0
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    timeframe: str = "1d"


class BacktestRunStatus(BaseModel):
    id: str
    name: str = ""
    status: str = "queued"
    progress_pct: float = 0.0
    message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None


class BacktestRunResponse(BaseModel):
    id: str
    name: str = ""
    strategy_type: str = ""
    symbols: list[str] = Field(default_factory=list)
    status: str = "queued"
    progress_pct: float = 0.0
    initial_capital: float = 0.0
    current_value: float = 0.0
    total_return_pct: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
