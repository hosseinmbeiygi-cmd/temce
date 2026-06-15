from __future__ import annotations

from pydantic import BaseModel, Field


class MetalRequest(BaseModel):
    symbol: str = ""
    name: str = ""
    category: str = "precious"
    unit: str = "oz"


class MetalResponse(BaseModel):
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


class MetalListResponse(BaseModel):
    items: list[MetalResponse] = Field(default_factory=list)
    total: int = 0
