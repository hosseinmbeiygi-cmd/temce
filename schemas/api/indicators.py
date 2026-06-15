from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class IndicatorRequest(BaseModel):
    symbol: str
    indicator_type: str = "sma"
    params: dict[str, Any] = Field(default_factory=lambda: {"period": 14})
    start_date: date | None = None
    end_date: date | None = None
    timeframe: str = "1d"


class IndicatorResponse(BaseModel):
    symbol: str = ""
    indicator_type: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    values: list[dict[str, Any]] = Field(default_factory=list)
    timeframe: str = "1d"
    generated_at: str = ""


class IndicatorListResponse(BaseModel):
    items: list[IndicatorResponse] = Field(default_factory=list)
    total: int = 0
