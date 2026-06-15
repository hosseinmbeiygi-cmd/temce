from __future__ import annotations

from pydantic import BaseModel, Field


class IndexRequest(BaseModel):
    symbol: str = ""
    name: str = ""
    index_type: str = "market_cap_weighted"


class IndexResponse(BaseModel):
    id: str
    symbol: str = ""
    name: str = ""
    index_type: str = ""
    value: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    high_today: float = 0.0
    low_today: float = 0.0
    constituents_count: int = 0
    last_updated: str = ""


class IndexListResponse(BaseModel):
    items: list[IndexResponse] = Field(default_factory=list)
    total: int = 0
