"""Adapter: BrsApi_Forecasting Redis logic روی core/cache.py اصلی (ایمن، بدون اتصال مستقیم)."""

from __future__ import annotations

import json
import time

from core.cache import get_cache
from src.forecast_engine.config import (
    RAW_PRICE_CACHE_TTL_SECONDS,
    REDIS_KEY_LAST_UPDATE,
    REDIS_KEY_RAW_PRICE,
)


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
