from __future__ import annotations

from pydantic import BaseModel, Field


class FundRequest(BaseModel):
    symbol: str = ""
    name: str = ""
    fund_type: str = "etf"
    manager: str = ""


class FundResponse(BaseModel):
    id: str
    symbol: str = ""
    name: str = ""
    fund_type: str = ""
    manager: str = ""
    nav: float = 0.0
    nav_date: str = ""
    total_assets: float = 0.0
    units_outstanding: int = 0
    status: str = "active"


class FundListResponse(BaseModel):
    items: list[FundResponse] = Field(default_factory=list)
    total: int = 0
