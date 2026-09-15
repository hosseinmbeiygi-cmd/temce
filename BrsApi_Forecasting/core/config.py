"""
core/config.py — پیکربندی مرکزی، گاردریل‌ها و ثابت‌های سیستم.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class InfraSettings:
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./brsapi_forecast.db")


INFRA = InfraSettings()

VALID_RANGES: dict[str, dict[str, float]] = {
    "XAU_USD": {"min": 1500, "max": 6000},
    "USD_IRR_FREE": {"min": 200_000, "max": 3_000_000},
}

STALE_DATA_MAX_AGE_SECONDS: int = 300

DEFAULT_DAILY_MAX_JUMP_PCT: float = 0.08
DEFAULT_INTRADAY_MAX_JUMP_PCT: float = 0.05

EMA_PERIOD: int = 14
TROY_OUNCE_GRAMS: float = 31.1034768
GOLD_PURITY_REFERENCE: float = 24.0

RAW_PRICE_CACHE_TTL_SECONDS: int = STALE_DATA_MAX_AGE_SECONDS

REDIS_KEY_RAW_PRICE = "live_rates:{symbol}"
REDIS_KEY_EMA_BUBBLE = "forecasting:ema_bubble:{symbol}"
REDIS_KEY_LAST_UPDATE = "forecasting:last_update:{symbol}"
