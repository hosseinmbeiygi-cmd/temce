from __future__ import annotations

from pydantic import BaseModel, Field


class OhlcvRequest(BaseModel):
    symbol: str
    start_date: str = ""
    end_date: str = ""
    timeframe: str = "1d"
    adjust: bool = False


class OhlcvResponse(BaseModel):
    date: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    value: float = 0.0
    trade_count: int = 0


class OhlcvListResponse(BaseModel):
    symbol: str = ""
    timeframe: str = "1d"
    items: list[OhlcvResponse] = Field(default_factory=list)
    total: int = 0
