"""Coin Bubble — سکه بهار آزادی vs ارزش ذاتی اونس."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CoinBubbleRequest(BaseModel):
    """ورودی محاسبه حباب سکه. تمام مبالغ ریالی بر حسب **ریال** هستند."""

    coin_price_irr: float = Field(..., gt=0, description="قیمت بازار سکه (ریال)")
    gold_oz_usd: float = Field(..., gt=0, description="قیمت اونس جهانی (USD)")
    usd_irr: float = Field(..., gt=0, description="نرخ دلار آزاد (ریال — مثلاً 605_000_000 برای 60.5k تومان)")
    weight_g: float = Field(default=8.133, gt=0, description="وزن سکه (گرم)")
    purity: float = Field(default=0.915, gt=0, le=1, description="عیار ضرب + اجرت")


class CoinBubbleResponse(BaseModel):
    """خروجی محاسبه حباب/تخفیف سکه. مبالغ بر حسب ریال."""

    coin_intrinsic_irr: float = Field(..., description="ارزش ذاتی سکه بر اساس اونس (ریال)")
    coin_market_irr: float = Field(..., description="قیمت بازار سکه (ریال)")
    bubble_pct: float = Field(..., description="درصد حباب (مثبت) یا تخفیف (منفی)")
    signal: str = Field(..., description="BUY / SELL / NEUTRAL")
    reason: str = Field(..., description="توضیح سیگنال")
    inputs: CoinBubbleRequest
