"""Adapter: BrsApi_Forecasting Redis logic روی core/cache.py اصلی (ایمن، بدون اتصال مستقیم).

همچنین کش خلاصهٔ طلا (gold summary) برای endpoint خلاصهٔ /gold/analytics را نگه می‌دارد.
"""

from __future__ import annotations

import json
import time
from typing import Any

from core.cache import get_cache
from src.forecast_engine.config import (
    RAW_PRICE_CACHE_TTL_SECONDS,
    REDIS_KEY_LAST_UPDATE,
    REDIS_KEY_RAW_PRICE,
)

REDIS_KEY_GOLD_SUMMARY = "golddesk:gold_summary:latest"


async def cache_raw_price(symbol: str, price: float) -> None:
    cache = get_cache()
    payload = json.dumps({"price": price, "timestamp": time.time()})
    await cache.set(REDIS_KEY_RAW_PRICE.format(symbol=symbol), payload, ttl=RAW_PRICE_CACHE_TTL_SECONDS)
    await cache.set(REDIS_KEY_LAST_UPDATE.format(symbol=symbol), time.time(), ttl=RAW_PRICE_CACHE_TTL_SECONDS)


async def get_raw_price(symbol: str) -> dict | None:
    cache = get_cache()
    raw = await cache.get(REDIS_KEY_RAW_PRICE.format(symbol=symbol))
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None


async def get_previous_ema(key: str) -> float | None:
    cache = get_cache()
    val = await cache.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None


async def set_ema(key: str, value: float) -> None:
    cache = get_cache()
    # persistent — EMA نباید با TTL پاک شود
    await cache.set_persistent(key, value)


async def health_check() -> bool:
    cache = get_cache()
    return await cache.ping()


async def get_cached_gold_summary() -> dict[str, Any] | None:
    cache = get_cache()
    raw = await cache.get(REDIS_KEY_GOLD_SUMMARY)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None


async def set_cached_gold_summary(data: dict[str, Any], ttl: int = 10) -> None:
    cache = get_cache()
    payload = json.dumps(data)
    await cache.set(REDIS_KEY_GOLD_SUMMARY, payload, ttl=ttl)
