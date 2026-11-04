from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

from schemas.api.currency import CurrencyCode, currency_field, toman


class EnergyRequest(BaseModel):
    symbol: str = ""
    name: str = ""
    category: str = "oil"
    unit: str = "barrel"


class EnergyResponse(BaseModel):
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

    @computed_field(description="قیمت به تومان (TMN)")  # type: ignore[prop-decorator]
    @property
    def price_toman(self) -> float:
        return toman(self.price)


class EnergyListResponse(BaseModel):
    items: list[EnergyResponse] = Field(default_factory=list)
    total: int = 0
