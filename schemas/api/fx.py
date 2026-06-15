from __future__ import annotations

from pydantic import BaseModel, Field


class FxRateRequest(BaseModel):
    base_currency: str = "USD"
    quote_currency: str = "IRR"


class FxRateResponse(BaseModel):
    id: str
    pair: str = ""
    base_currency: str = ""
    quote_currency: str = ""
    rate: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    change_pct: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    source: str = ""
    last_updated: str = ""


class FxRateListResponse(BaseModel):
    items: list[FxRateResponse] = Field(default_factory=list)
    total: int = 0
