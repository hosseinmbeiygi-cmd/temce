from __future__ import annotations

from pydantic import BaseModel


class QuoteResponse(BaseModel):
    id: str
    instrument_id: str
    symbol: str = ""
    price_close: float = 0.0
    price_open: float = 0.0
    price_high: float = 0.0
    price_low: float = 0.0
    price_change: float = 0.0
    price_change_pct: float = 0.0
    volume: int = 0
    value: float = 0.0
    time: str = ""
    date: str = ""


class QuoteListResponse(BaseModel):
    items: list[QuoteResponse]
    total: int
    page: int
    page_size: int
