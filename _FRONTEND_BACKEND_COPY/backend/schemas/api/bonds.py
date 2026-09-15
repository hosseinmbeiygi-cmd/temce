from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class BondRequest(BaseModel):
    symbol: str = ""
    isin: str = ""
    name: str = ""
    issuer: str = ""
    par_value: float = 1_000_000
    coupon_rate: float = 0.0
    maturity_date: date | None = None
    issue_date: date | None = None


class BondResponse(BaseModel):
    id: str
    symbol: str = ""
    isin: str = ""
    name: str = ""
    issuer: str = ""
    par_value: float = 0.0
    coupon_rate: float = 0.0
    maturity_date: str = ""
    issue_date: str = ""
    price: float = 0.0
    yield_pct: float = 0.0
    duration: float = 0.0
    status: str = "active"
    created_at: str = ""


class BondListResponse(BaseModel):
    items: list[BondResponse] = Field(default_factory=list)
    total: int = 0
