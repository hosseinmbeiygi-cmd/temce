"""API-03: aggregate-cache invalidation must reach the other API processes.

The sync worker and the API run in different containers, so the previous
``_AGG_CACHE.clear()`` only reached the process that happened to run the sync;
every other API worker kept serving pre-sync aggregates for the full 5-minute
TTL. The fix publishes a generation token to L2 (Redis): a process that sees a
new token drops its local entries.

These tests drive the cache helpers and one real endpoint with a fake L2 — no
Redis server, no PostgreSQL. They also pin the two degraded paths:

* one L2 read per process per interval (polling widgets must not pay a Redis
  round-trip per request), and
* Redis being down leaves the local TTL behaviour intact and never fails a
  request.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from apps.api.endpoints import market as market_ep
from core.cache_manager import set_cache_manager

SNAPSHOT = {
    "symbol": "فولاد",
    "name": "فولاد مبارکه",
    "market_value": 5e12,
    "fetched_at": "2026-10-29T09:30:00+00:00",
}


class _FakeCacheManager:
    """Stand-in for ``core.cache_manager.CacheManager`` (L2 only)."""

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.down = False
        self.gets = 0
        self.sets = 0

    async def get(self, key: str) -> Any | None:
        self.gets += 1
        if self.down:
            raise RuntimeError("redis down")
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.sets += 1
        if self.down:
            raise RuntimeError("redis down")
        self.store[key] = value


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeCacheManager()
    set_cache_manager(fake)  # type: ignore[arg-type]
    market_ep._AGG_CACHE.clear()
    market_ep._agg_publish_tasks.clear()
    monkeypatch.setattr(market_ep, "_agg_local_token", None)
    monkeypatch.setattr(market_ep, "_agg_token_checked_at", 0.0)
    yield fake
    market_ep._AGG_CACHE.clear()
    market_ep._agg_publish_tasks.clear()
    set_cache_manager(None)


def _brsapi() -> SimpleNamespace:
    return SimpleNamespace(
        get_latest_snapshots=AsyncMock(return_value=[dict(SNAPSHOT)])
    )


# ── Publishing ──────────────────────────────────────────────────────────────


async def test_invalidate_publishes_a_generation_token(_isolated_cache) -> None:
    market_ep.invalidate_agg_cache()

    pending = list(market_ep._agg_publish_tasks)
    assert pending, "invalidate must schedule the L2 publish"
    await asyncio.gather(*pending)

    token = _isolated_cache.store[market_ep._AGG_TOKEN_KEY]
    assert isinstance(token, str) and token
    assert market_ep._agg_local_token == token


def test_invalidate_outside_an_event_loop_still_clears_locally(_isolated_cache) -> None:
    market_ep._agg_cache_set("k", [1], as_of="t")

    market_ep.invalidate_agg_cache()

    assert market_ep._AGG_CACHE == {}
    assert market_ep._AGG_TOKEN_KEY not in _isolated_cache.store


# ── Adopting another process's invalidation ────────────────────────────────


async def test_a_foreign_token_drops_this_process_copy(_isolated_cache) -> None:
    market_ep._agg_cache_set("k", [1], as_of="t")
    _isolated_cache.store[market_ep._AGG_TOKEN_KEY] = "other-process-token"

    value, _as_of = await market_ep._agg_cache_get("k")

    assert value is None, "another process invalidated the aggregate"
    assert market_ep._AGG_CACHE == {}
    assert market_ep._agg_local_token == "other-process-token"


async def test_own_token_keeps_the_cached_value(_isolated_cache) -> None:
    token = await market_ep.publish_agg_invalidation()
    market_ep._agg_cache_set("k", [1], as_of="t")
    assert _isolated_cache.store[market_ep._AGG_TOKEN_KEY] == token

    value, as_of = await market_ep._agg_cache_get("k")

    assert (value, as_of) == ([1], "t")


# ── Throttling and degraded Redis ──────────────────────────────────────────


async def test_token_checks_are_throttled_per_process(
    _isolated_cache, monkeypatch: pytest.MonkeyPatch
) -> None:
    market_ep._agg_cache_set("k", [1], as_of="t")
    await market_ep._agg_cache_get("k")
    reads_after_first = _isolated_cache.gets

    # A different token appears, but the interval has not elapsed yet.
    _isolated_cache.store[market_ep._AGG_TOKEN_KEY] = "newer"
    value, _as_of = await market_ep._agg_cache_get("k")
    assert value == [1]
    assert _isolated_cache.gets == reads_after_first, "no L2 read inside the interval"

    # Once the interval elapses the new token wins.
    monkeypatch.setattr(
        market_ep, "_agg_token_checked_at", time.monotonic() - market_ep._AGG_TOKEN_CHECK_INTERVAL - 1
    )
    value, _as_of = await market_ep._agg_cache_get("k")
    assert value is None


async def test_redis_down_degrades_to_local_ttl(_isolated_cache) -> None:
    market_ep._agg_cache_set("k", [1], as_of="t")
    _isolated_cache.down = True

    value, as_of = await market_ep._agg_cache_get("k")

    assert (value, as_of) == ([1], "t"), "a dead L2 must not fail or empty a warm cache"


# ── Endpoint behaviour end to end (no DB, no Redis) ────────────────────────


async def test_endpoint_refetches_after_a_foreign_invalidation(_isolated_cache) -> None:
    brsapi = _brsapi()

    first = await market_ep.market_asset_allocation(limit=2000, brsapi=brsapi)
    second = await market_ep.market_asset_allocation(limit=2000, brsapi=brsapi)
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert brsapi.get_latest_snapshots.await_count == 1

    # The sync worker (another container) publishes a new generation.
    _isolated_cache.store[market_ep._AGG_TOKEN_KEY] = "sync-worker-token"
    market_ep._agg_token_checked_at = 0.0

    third = await market_ep.market_asset_allocation(limit=2000, brsapi=brsapi)

    assert third.cache_hit is False, "the stale aggregate must not survive the sync"
    assert brsapi.get_latest_snapshots.await_count == 2


def test_token_outlives_the_cache_it_protects() -> None:
    """A token that expires sooner than the cache would resurrect stale entries."""
    assert market_ep._AGG_TOKEN_TTL > market_ep._AGG_TTL
    assert market_ep._AGG_TOKEN_CHECK_INTERVAL < market_ep._AGG_TTL


# ── Two module instances, one real Redis (the actual cross-process path) ───


def _load_market_copy(alias: str):
    """Load ``apps/api/endpoints/market.py`` as an independent module object.

    Two copies of the module have separate ``_AGG_CACHE`` globals — the same
    isolation two API processes have — while sharing the process-wide
    ``CacheManager`` (each real process has its own connection to the same
    Redis). This is the closest off-line proof of the cross-process path.
    """
    import importlib.util

    path = Path(market_ep.__file__)
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


async def test_real_redis_invalidation_reaches_the_other_instance(monkeypatch) -> None:
    """Process B stops serving its cached aggregate after process A's sync."""
    import uuid

    from core.cache_manager import CacheManager
    from core.config import settings

    manager = CacheManager(
        redis_url=settings.redis_url,
        namespace=f"test_api03_{uuid.uuid4().hex[:8]}",
        default_ttl=60,
    )
    if not await manager._ensure_redis():
        await manager.close()
        pytest.skip("Redis is not reachable on this machine")
    set_cache_manager(manager)

    process_a = _load_market_copy(f"_market_a_{uuid.uuid4().hex[:6]}")
    process_b = _load_market_copy(f"_market_b_{uuid.uuid4().hex[:6]}")
    try:
        # B serves and caches an aggregate.
        process_b._agg_cache_set("k", ["stale"], as_of="2026-10-29T09:30:00+00:00")
        value, _as_of = await process_b._agg_cache_get("k")
        assert value == ["stale"]

        # A runs the sync in its own container and publishes the token.
        process_a.invalidate_agg_cache()
        pending = list(process_a._agg_publish_tasks)
        assert pending
        await asyncio.gather(*pending)

        # B's next read observes the foreign token and drops its copy.
        monkeypatch.setattr(process_b, "_agg_token_checked_at", 0.0)
        value, _as_of = await process_b._agg_cache_get("k")

        assert value is None
        assert process_b._AGG_CACHE == {}
        assert process_b._agg_local_token == process_a._agg_local_token
    finally:
        await manager.invalidate(process_a._AGG_TOKEN_KEY)
        await manager.close()
        set_cache_manager(None)
        sys.modules.pop(process_a.__name__, None)
        sys.modules.pop(process_b.__name__, None)
