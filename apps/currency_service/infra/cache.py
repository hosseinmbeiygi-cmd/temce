"""Redis-backed overview cache (TTL from settings, default 10s).

Falls back to direct computation when Redis is down — ``get_cache()``
returns a NullCache-compatible service and every miss recomputes.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from core.cache import get_cache
from core.logging import get_logger

logger = get_logger(__name__)

_KEY = "currency:overview"


async def cached_overview(
    compute: Callable[[], Awaitable[dict[str, Any]]],
    ttl: int,
) -> dict[str, Any]:
    cache = get_cache()
    try:
        hit = await cache.get(_KEY)
        if hit is not None:
            return hit
    except Exception:
        logger.warning("currency cache read failed; recomputing", exc_info=True)

    payload = await compute()
    try:
        await cache.set(_KEY, payload, ttl=ttl)
    except Exception:
        logger.warning("currency cache write failed", exc_info=True)
    return payload