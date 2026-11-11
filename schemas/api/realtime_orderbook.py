from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

from schemas.api.currency import CurrencyCode, currency_field, toman


class OrderBookLevel(BaseModel):
    """One price level. ``price`` stays rial; ``price_toman`` is TMN."""

    price: float = 0.0
    volume: int = 0
    count: int = 0
    currency: CurrencyCode = currency_field()

    @computed_field(description="قیمت سطح سفارش به تومان (TMN)")  # type: ignore[prop-decorator]
    @property
    def price_toman(self) -> float:
        return toman(self.price)


class OrderBookSnapshot(BaseModel):
    symbol: str = ""
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)
    timestamp: str = ""
    exchange: str = "tsetmc"
