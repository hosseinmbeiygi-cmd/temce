"""Live gold prices (BrsApi feed)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoldLivePricesRequest(BaseModel):
    """درخواست قیمت لحظه‌ای — اختیاری."""

    refresh: bool = Field(default=False, description="اجبار به بازخوانی از منبع (نه کش)")


class GoldLivePrices(BaseModel):
    """قیمت‌های زنده بازار طلا."""

    gold_oz_usd: float = Field(..., description="اونس جهانی (USD)")
    gold_18k_irr: float = Field(..., description="طلای ۱۸ عیار هر گرم (تومان)")
    coin_bahar_irr: float = Field(..., description="سکه بهار آزادی (تومان)")
    usd_irr: float = Field(..., description="دلار آزاد (تومان)")
    last_updated: str
    source: str = "BrsApi.ir"
    is_stale: bool = Field(default=False, description="True اگر داده از کش منقضی باشد")
