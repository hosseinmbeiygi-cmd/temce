from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, computed_field

from schemas.api.currency import CurrencyCode, currency_field, toman


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
    currency: CurrencyCode = currency_field()

    @computed_field(description="قیمت اوراق به تومان (TMN)")
    @property
    def price_toman(self) -> float:
        return toman(self.price)

    @computed_field(description="ارزش اسمی به تومان (TMN)")
    @property
    def par_value_toman(self) -> float:
        return toman(self.par_value)


class BondListResponse(BaseModel):
    items: list[BondResponse] = Field(default_factory=list)
    total: int = 0
