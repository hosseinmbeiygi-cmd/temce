from __future__ import annotations

from pydantic import BaseModel


class RealtimeQuoteResponse(BaseModel):
    symbol: str = ""
    last_price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    close: float = 0.0
    volume: int = 0
    value: float = 0.0
    bid_price: float = 0.0
    bid_volume: int = 0
    ask_price: float = 0.0
    ask_volume: int = 0
    timestamp: str = ""


class QuoteStreamMessage(BaseModel):
    type: str = "quote"
    data: RealtimeQuoteResponse
    stream: str = "quotes"
