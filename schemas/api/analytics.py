from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsRequest(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    indicators: list[str] = Field(default_factory=lambda: ["sma", "ema", "rsi"])
    timeframe: str = "1d"


class AnalyticsResponse(BaseModel):
    symbol: str
    timeframe: str = "1d"
    indicators: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""


class MarketAnalyticsSummary(BaseModel):
    total_instruments: int = 0
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    total_volume: float = 0.0
    total_value: float = 0.0
    market_cap: float = 0.0
