from __future__ import annotations

from pydantic import BaseModel, computed_field

from schemas.api.currency import CurrencyCode, currency_field, toman


class TradeSnapshot(BaseModel):
    """Realtime print. ``price``/``value`` are rial; ``*_toman`` are TMN."""

    symbol: str = ""
    price: float = 0.0
    volume: int = 0
    value: float = 0.0
    side: str = ""
    timestamp: str = ""
    trade_id: str = ""
    currency: CurrencyCode = currency_field()

    @computed_field(description="قیمت معامله به تومان (TMN)")
    @property
    def price_toman(self) -> float:
        return toman(self.price)

    @computed_field(description="ارزش معامله به تومان (TMN)")
    @property
    def value_toman(self) -> float:
        return toman(self.value)


class TradeStreamMessage(BaseModel):
    type: str = "trade"
    data: TradeSnapshot
    stream: str = "trades"
