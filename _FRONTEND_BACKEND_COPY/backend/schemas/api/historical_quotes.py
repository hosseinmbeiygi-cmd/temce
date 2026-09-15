from __future__ import annotations

from pydantic import BaseModel, Field


class QuoteHistoryRequest(BaseModel):
    symbol: str
    start_date: str = ""
    end_date: str = ""
    timeframe: str = "1d"
    fields: list[str] | None = None


class QuoteHistoryResponse(BaseModel):
    id: str = ""
    instrument_id: str = ""
    symbol: str = ""
    date: str = ""
    time: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    last: float = 0.0
    volume: int = 0
    value: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0


class QuoteListResponse(BaseModel):
    symbol: str = ""
    timeframe: str = "1d"
    items: list[QuoteHistoryResponse] = Field(default_factory=list)
    total: int = 0
