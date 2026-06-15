from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HistoricalDataRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    timeframe: str = "1d"
    adjust: bool = False
    fields: list[str] | None = None


class HistoricalDataResponse(BaseModel):
    symbol: str = ""
    timeframe: str = ""
    data: list[dict[str, Any]] = Field(default_factory=list)
    total_records: int = 0
    source: str = ""
    retrieved_at: str = ""
