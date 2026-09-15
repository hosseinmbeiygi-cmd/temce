"""Market data cache — wraps CacheManager for market-specific caching.

Provides consistent TTL defaults and cache-key naming for the heavy
read-only market endpoints (gainers, losers, heatmap, sparklines, etc.).

Usage::

    from services.market_cache import market_cache

    result = await market_cache.get_or_compute(
        key="market:gainers:20",
        ttl=30,
        func=lambda: service.get_top_gainers(20),
    )
"""

from __future__ import annotations

from typing import Any

from core.cache_manager import get_cache_manager
from core.logging import get_logger

logger = get_logger(__name__)

# ── TTL defaults (seconds) ──────────────────────────────────────────
# These reflect how stale each data source can safely be.
TTL_GAINER_LOSER = 30  # gainers / losers / active — re-rank every 30s
TTL_SNAPSHOT = 60  # snapshots (heatmap, enriched-heatmap, treemap)
TTL_SPARKLINES = 120  # historical close prices — change slowly
TTL_OVERVIEW = 30  # market overview (total volume, value)
TTL_INDICES = 30  # TSE / FaraBourse indices
TTL_MARKET_WATCH = 60  # comprehensive market-watch dashboard
TTL_DASHBOARD = 45  # aggregated market-dashboard
TTL_COMMODITY = 300  # commodity prices — change slowly
TTL_CRYPTO = 120  # crypto prices
TTL_NEWS = 180  # news headlines
TTL_CURRENCY_GOLD = 120  # currency / gold prices


async def get_or_compute(key: str, ttl: int, func: Any) -> Any:
    """Thin wrapper around CacheManager.get_or_compute."""
    cm = get_cache_manager()
    return await cm.get_or_compute(key=key, ttl=ttl, func=func)


async def invalidate(*keys: str) -> None:
    """Invalidate one or more cache keys across all layers."""
    cm = get_cache_manager()
    for key in keys:
        await cm.invalidate(key)


async def clear_market_cache() -> int:
    """Clear all keys managed by the cache manager. Returns count cleared."""
    cm = get_cache_manager()
    count = len(cm.cached_keys)
    await cm.clear_all()
    return count
