from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

from schemas.api.currency import CurrencyCode, currency_field, toman


class OhlcvRequest(BaseModel):
    symbol: str
    start_date: str = ""
    end_date: str = ""
    timeframe: str = "1d"
    adjust: bool = False


class OhlcvResponse(BaseModel):
    date: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    value: float = 0.0
    trade_count: int = 0
    currency: CurrencyCode = currency_field()

    @computed_field(description="قیمت پایانی به تومان (TMN)")  # type: ignore[prop-decorator]
    @property
    def close_toman(self) -> float:
        return toman(self.close)

    @computed_field(description="ارزش معاملات به تومان (TMN)")  # type: ignore[prop-decorator]
    @property
    def value_toman(self) -> float:
        return toman(self.value)


class OhlcvListResponse(BaseModel):
    symbol: str = ""
    timeframe: str = "1d"
    items: list[OhlcvResponse] = Field(default_factory=list)
    total: int = 0
