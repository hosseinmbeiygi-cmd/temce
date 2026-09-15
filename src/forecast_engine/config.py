"""ادغام config از BrsApi_Forecasting/core/config.py — با تنظیمات اصلی پروژه هم‌راستا."""

from __future__ import annotations

# گاردریل‌های کیفیت داده — از BrsApi_Forecasting/core/config.py
VALID_RANGES: dict[str, dict[str, float]] = {
    "XAU_USD": {"min": 1500, "max": 6000},
    "USD_IRR_FREE": {"min": 200_000, "max": 3_000_000},
}

STALE_DATA_MAX_AGE_SECONDS: int = 300

DEFAULT_DAILY_MAX_JUMP_PCT: float = 0.08
DEFAULT_INTRADAY_MAX_JUMP_PCT: float = 0.05

# پارامترهای موتور پیش‌بینی
EMA_PERIOD: int = 14
TROY_OUNCE_GRAMS: float = 31.1034768
GOLD_PURITY_REFERENCE: float = 24.0

RAW_PRICE_CACHE_TTL_SECONDS: int = STALE_DATA_MAX_AGE_SECONDS

REDIS_KEY_RAW_PRICE = "live_rates:{symbol}"
REDIS_KEY_EMA_BUBBLE = "forecasting:ema_bubble:{symbol}"
REDIS_KEY_LAST_UPDATE = "forecasting:last_update:{symbol}"
