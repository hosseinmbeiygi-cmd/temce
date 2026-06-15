from __future__ import annotations

from pydantic import BaseModel, Field


class CommodityRequest(BaseModel):
    symbol: str = ""
    name: str = ""
    category: str = "metal"
    unit: str = "kg"


class CommodityResponse(BaseModel):
    id: str
    symbol: str = ""
    name: str = ""
    category: str = ""
    unit: str = ""
    price: float = 0.0
    price_change_pct: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    last_updated: str = ""


class CommodityListResponse(BaseModel):
    items: list[CommodityResponse] = Field(default_factory=list)
    total: int = 0
