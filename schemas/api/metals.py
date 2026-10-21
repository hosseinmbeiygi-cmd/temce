from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

from schemas.api.currency import CurrencyCode, currency_field, toman


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
    currency: CurrencyCode = currency_field()

    @computed_field(description="قیمت به تومان (TMN)")
    @property
    def price_toman(self) -> float:
        return toman(self.price)


class MetalListResponse(BaseModel):
    items: list[MetalResponse] = Field(default_factory=list)
    total: int = 0
