from __future__ import annotations

from pydantic import BaseModel, Field


class ForecastResponse(BaseModel):
    symbol: str
    fair_value: float | None = None
    current_market_price: float
    current_bubble: float | None = None
    forecasted_bubble: float | None = None
    forecasted_price: float
    bubble_trend: str


class SymbolStatus(BaseModel):
    status: str
    message: str | None = None


class BulkForecastResponse(BaseModel):
    success: bool
    data: dict[str, ForecastResponse | SymbolStatus]
    meta: dict[str, int]


class PriceIngestRequest(BaseModel):
    symbol: str
    price: float = Field(gt=0)
