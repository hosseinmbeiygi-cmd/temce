from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

from schemas.api.currency import CurrencyCode, currency_field, toman


class QuoteHistoryRequest(BaseModel):
    symbol: str
    start_date: str = ""
    end_date: str = ""
    timeframe: str = "1d"
    fields: list[str] | None = None


class QuoteHistoryResponse(BaseModel):
    id: str = ""
    instrument_id: str = ""
    symbol: str = ""
    date: str = ""
    time: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    last: float = 0.0
    volume: int = 0
    value: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    currency: CurrencyCode = currency_field()

    @computed_field(description="قیمت پایانی به تومان (TMN)")
    @property
    def close_toman(self) -> float:
        return toman(self.close)

    @computed_field(description="آخرین قیمت به تومان (TMN)")
    @property
    def last_toman(self) -> float:
        return toman(self.last)

    @computed_field(description="ارزش معاملات به تومان (TMN)")
    @property
    def value_toman(self) -> float:
        return toman(self.value)


class QuoteListResponse(BaseModel):
    symbol: str = ""
    timeframe: str = "1d"
    items: list[QuoteHistoryResponse] = Field(default_factory=list)
    total: int = 0
