from __future__ import annotations

import json
import time
from functools import lru_cache

from redis.asyncio import Redis

from core.config import INFRA, RAW_PRICE_CACHE_TTL_SECONDS, REDIS_KEY_LAST_UPDATE, REDIS_KEY_RAW_PRICE


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    return Redis(
        host=INFRA.redis_host,
        port=INFRA.redis_port,
        db=INFRA.redis_db,
        decode_responses=True,
    )


async def cache_raw_price(symbol: str, price: float) -> None:
    redis = get_redis()
    payload = json.dumps({"price": price, "timestamp": time.time()})
    key = REDIS_KEY_RAW_PRICE.format(symbol=symbol)
    await redis.set(key, payload, ex=RAW_PRICE_CACHE_TTL_SECONDS)
    await redis.set(REDIS_KEY_LAST_UPDATE.format(symbol=symbol), time.time())


async def get_raw_price(symbol: str) -> dict | None:
    redis = get_redis()
    raw = await redis.get(REDIS_KEY_RAW_PRICE.format(symbol=symbol))
    if raw is None:
        return None
    return json.loads(raw)


async def get_previous_ema(key: str) -> float | None:
    redis = get_redis()
    val = await redis.get(key)
    return float(val) if val is not None else None


async def set_ema(key: str, value: float) -> None:
    redis = get_redis()
    await redis.set(key, value)


async def health_check() -> bool:
    try:
        redis = get_redis()
        return bool(await redis.ping())
    except Exception:
        return False
