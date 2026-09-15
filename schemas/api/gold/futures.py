"""Futures — محاسبات مارجین، لیکوئیدیشن و سلامت پوزیشن (IME Coin Futures)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FuturesMarginRequest(BaseModel):
    """ورودی کلکولاتور مارجین آتی سکه (IME)."""

    entry_price: float = Field(..., gt=0, description="قیمت ورود (تومان)")
    position_type: str = Field(..., pattern="^(LONG|SHORT)$")
    leverage: int = Field(default=10, ge=1, le=20, description="اهرم (پیش‌فرض 10)")
    quantity: int = Field(..., gt=0, description="تعداد قرارداد (هر قرارداد = 10 سکه)")
    current_price: float | None = Field(None, gt=0, description="قیمت فعلی (برای Health Ratio)")
    account_equity: float | None = Field(None, gt=0, description="موجودی حساب (تومان)")


class FuturesMarginResponse(BaseModel):
    """خروجی کلکولاتور."""

    contract_value: float = Field(..., description="ارزش ناخالص پوزیشن (تومان)")
    initial_margin: float = Field(..., description="مارجین اولیه (10%)")
    maintenance_margin: float = Field(..., description="مارجین نگهداری (5%)")
    liquidation_price: float = Field(..., description="قیمت لیکوئیدیشن")
    leverage: int
    position_type: str
    # اختیاری: فقط وقتی current_price/account_equity داده شود
    health_ratio: float | None = None
    distance_to_liquidation_pct: float | None = None
    alert_level: str | None = Field(None, description="SAFE / WARNING / CRITICAL")
    alert_message: str | None = None
    recommended_stop_loss: float | None = None


class FuturesPosition(BaseModel):
    """نمایش یک پوزیشن باز (برای جدول)."""

    id: str
    symbol: str
    position_type: str
    entry_price: float
    current_price: float | None
    quantity: int
    unrealized_pnl_pct: float | None
    unrealized_pnl_irr: float | None
    liquidation_price: float
    distance_to_liquidation_pct: float | None
    health_ratio: float | None
    leverage: int
    status: str = "OPEN"


class FuturesHealthResponse(BaseModel):
    """پاسخ سلامت پورتفولیو آتی."""

    positions: list[FuturesPosition] = Field(default_factory=list)
    total_used_margin: float = 0.0
    total_equity: float = 0.0
    aggregate_health_ratio: float | None = None
    critical_count: int = 0
    warning_count: int = 0
