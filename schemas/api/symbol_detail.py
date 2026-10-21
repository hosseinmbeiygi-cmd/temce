from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from schemas.api.currency import CurrencyCode, currency_field, toman


class SymbolDetailResponse(BaseModel):
    """Symbol snapshot. Raw price fields are rial; ``*_toman`` are TMN."""

    ins_code: str = Field(default="", description="کد نماد")
    symbol: str = Field(default="", description="نماد")
    company_name: str = Field(default="", description="نام شرکت")
    last_price: float = Field(default=0.0, description="قیمت آخرین معامله")
    closing_price: float = Field(default=0.0, description="قیمت پایانی")
    volume: int = Field(default=0, description="حجم معاملات")
    value: float = Field(default=0.0, description="ارزش معاملات")
    trades_count: int = Field(default=0, description="تعداد معاملات")
    yesterday_price: float = Field(default=0.0, description="قیمت دیروز")
    open_price: float = Field(default=0.0, description="قیمت باز")
    high: float = Field(default=0.0, description="بیشترین")
    low: float = Field(default=0.0, description="کمترین")
    market_status: str = Field(default="", description="وضعیت بازار")
    base_volume: int = Field(default=0, description="حجم مبنا")
    shares_count: int = Field(default=0, description="تعداد سهام")
    industry_index: str = Field(default="", description="شاخص صنعت")
    created_at: datetime | None = None
    updated_at: datetime | None = None
    currency: CurrencyCode = currency_field()

    @computed_field(description="قیمت آخرین معامله به تومان (TMN)")
    @property
    def last_price_toman(self) -> float:
        return toman(self.last_price)

    @computed_field(description="قیمت پایانی به تومان (TMN)")
    @property
    def closing_price_toman(self) -> float:
        return toman(self.closing_price)

    @computed_field(description="ارزش معاملات به تومان (TMN)")
    @property
    def value_toman(self) -> float:
        return toman(self.value)
