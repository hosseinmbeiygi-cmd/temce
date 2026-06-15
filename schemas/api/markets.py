from __future__ import annotations

from pydantic import BaseModel, Field


class MarketOverview(BaseModel):
    market_type: str = ""
    total_instruments: int = 0
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    total_volume: float = 0.0
    total_value: float = 0.0
    total_trades: int = 0


class MarketSummaryResponse(BaseModel):
    timestamp: str = ""
    markets: list[MarketOverview] = Field(default_factory=list)
    total_market_cap: float = 0.0
    total_volume: float = 0.0
    total_value: float = 0.0
