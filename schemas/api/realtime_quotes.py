from __future__ import annotations

from pydantic import BaseModel, computed_field

from schemas.api.currency import CurrencyCode, currency_field, toman


class RealtimeQuoteResponse(BaseModel):
    """Realtime snapshot. Raw price fields are rial; ``*_toman`` are TMN."""

    symbol: str = ""
    last_price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    close: float = 0.0
    volume: int = 0
    value: float = 0.0
    bid_price: float = 0.0
    bid_volume: int = 0
    ask_price: float = 0.0
    ask_volume: int = 0
    timestamp: str = ""
    currency: CurrencyCode = currency_field()

    @computed_field(description="قیمت آخرین معامله به تومان (TMN)")  # type: ignore[prop-decorator]
    @property
    def last_price_toman(self) -> float:
        return toman(self.last_price)

    @computed_field(description="ارزش معاملات به تومان (TMN)")  # type: ignore[prop-decorator]
    @property
    def value_toman(self) -> float:
        return toman(self.value)


class QuoteStreamMessage(BaseModel):
    type: str = "quote"
    data: RealtimeQuoteResponse
    stream: str = "quotes"
