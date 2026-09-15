"""ETF Gold — NAV Premium/Discount for Iranian gold ETFs."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ETFSymbol(str, Enum):
    ZARFSHANG = "ZARFSHANG"
    LOTUS = "LOTUS"
    GOHAR = "GOHAR"
    SAMAN = "SAMAN"


# مرجع واحد برای استفاده در سراسر سرویس
ETF_UNIVERSE: dict[str, dict[str, str]] = {
    "ZARFSHANG": {
        "name_fa": "زرافشان",
        "isin": "IRO1ZARA0001",
        "management_fee": "0.5%",
    },
    "LOTUS": {
        "name_fa": "لوتوس",
        "isin": "IRO1LOTU0001",
        "management_fee": "0.5%",
    },
    "GOHAR": {
        "name_fa": "گوهر",
        "isin": "IRO1GOHA0001",
        "management_fee": "0.5%",
    },
    "SAMAN": {
        "name_fa": "ثامان",
        "isin": "IRO1SAMA0001",
        "management_fee": "0.5%",
    },
}


class ETFNavPremiumRow(BaseModel):
    """یک ردیف از جدول NAV Premium صندوق‌ها."""

    symbol: str
    name_fa: str
    isin: str
    market_price: float = Field(..., description="قیمت معاملاتی بازار (تومان)")
    nav: float = Field(..., description="NAV هر واحد (تومان)")
    premium_pct: float = Field(..., description="درصد پرمیوم (+) یا دیسکانت (-)")
    signal: str = Field(..., description="BUY / SELL / NEUTRAL")
    reason: str
    liquidity: str = "high"
    management_fee: str = "0.5%"


class ETFNavPremiumResponse(BaseModel):
    """پاسخ کامل: همه صندوق‌ها + سیگنال برتر."""

    items: list[ETFNavPremiumRow] = Field(default_factory=list)
    best_opportunity: str | None = Field(None, description="نماد با بهترین فرصت خرید")
    generated_at: str


# Re-export for convenience
ETFUniverse = ETF_UNIVERSE
