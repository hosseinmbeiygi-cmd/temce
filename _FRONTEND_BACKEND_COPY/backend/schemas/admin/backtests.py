from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BacktestAdminSchema(BaseModel):
    id: str
    name: str
    status: str = "draft"
    strategy_type: str = ""
    symbol: str = ""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 0.0
    total_return_pct: float | None = None
    created_by: str = "system"
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BacktestListResponse(BaseModel):
    items: list[BacktestAdminSchema] = Field(default_factory=list)
    total: int = 0
