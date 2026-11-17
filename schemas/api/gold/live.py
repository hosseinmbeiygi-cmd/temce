"""Live gold prices (BrsApi feed)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoldLivePricesRequest(BaseModel):
    """درخواست قیمت لحظه‌ای — اختیاری."""

    refresh: bool = Field(default=False, description="اجبار به بازخوانی از منبع (نه کش)")


class GoldLivePrices(BaseModel):
    """قیمت‌های زنده بازار طلا."""

    gold_oz_usd: float | None = Field(None, description="اونس جهانی (USD) — None اگر داده موجود نباشد")
    gold_18k_irr: float | None = Field(None, description="طلای ۱۸ عیار هر گرم (تومان) — None اگر داده موجود نباشد")
    coin_bahar_irr: float | None = Field(None, description="سکه بهار آزادی (تومان) — None اگر داده موجود نباشد")
    usd_irr: float | None = Field(None, description="دلار آزاد (تومان) — None اگر داده موجود نباشد")
    last_updated: str
    source: str = "BrsApi.ir"
    is_stale: bool = Field(default=False, description="True اگر داده از کش منقضی باشد")
