"""3-layer cache manager (L1 memory LRU + L2 Redis + L3 compute fallback).

Implements the ``CacheManager`` described in the platform upgrade plan:

* **L1 — memory**: thread-of-execution safe OrderedDict LRU (fast path).
* **L2 — Redis**: shared across workers/processes, TTL-based, pickle payloads.
* **L3 — compute**: when neither L1 nor L2 has the value, ``func()`` is
  awaited (typically a database read) and the result is promoted back to
  both L1 and L2.  If Redis is unavailable the manager degrades gracefully
  to L1-only caching — the value is still returned, just not shared.

Conventions follow ``core/cache.py`` (async ``get/set/delete`` + ``remember``)
but add an explicit LRU memory layer and optional DB-style fallback.

Usage::

    from core.cache_manager import get_cache_manager

    cm = get_cache_manager()
    value = await cm.get_or_compute("quote:خودرو", ttl=300, func=fetch_quote)
    await cm.invalidate("quote:خودرو")
    await cm.clear_all()
"""

from __future__ import annotations

import asyncio
import pickle
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class LRUCache:
    """Minimal ordered-dict LRU cache.

    ``get``/``put`` are O(1) and preserve access order.  Safe to use from a
    single asyncio event loop (the project's execution model).
    """

    def __init__(self, maxsize: int = 100) -> None:
        self.maxsize = max(1, int(maxsize))
        self._data: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any | None:
        if key not in self._data:
            return None
        # Move to end = most-recently-used.
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: str, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)  # evict least-recently-used

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    @property
    def keys(self) -> list[str]:
        return list(self._data.keys())


class CacheManager:
    """Three-layer cache: LRU memory -> Redis -> compute (DB fallback)."""

    def __init__(
        self,
        redis_url: str | None = None,
        max_memory_items: int = 100,
        default_ttl: int = 300,
        namespace: str = "cm",
    ) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._max_memory_items = max_memory_items
        self._default_ttl = default_ttl
        self._namespace = namespace
        self._l1 = LRUCache(maxsize=max_memory_items)
        self._redis: Any = None
        self._redis_connected: bool | None = None  # None = not probed yet
        self._keys: set[str] = set()  # keys written through this manager

    # ── Redis lifecycle ──────────────────────────────────────────────────

    async def _ensure_redis(self) -> bool:
        """Lazily connect to Redis. Returns True when usable.

        The result of a failed attempt is cached so we don't hammer a down
        server on every call; ``reset_redis_state()`` re-probes.
        """
        if self._redis is not None:
            return True
        if self._redis_connected is False:
            return False
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(self._redis_url, decode_responses=False)
            await client.ping()
            self._redis = client
            self._redis_connected = True
            logger.info("CacheManager connected to Redis at %s", self._redis_url)
            return True
        except Exception:
            self._redis_connected = False
            self._redis = None
            logger.warning("CacheManager Redis unavailable — using L1-only cache")
            return False

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.close()
            except Exception:
                pass
        self._redis = None
        self._redis_connected = None

    def reset_redis_state(self) -> None:
        """Force a re-probe of Redis on the next operation (after a restart)."""
        self._redis_connected = None

    @property
    def memory_size(self) -> int:
        return len(self._l1)

    @property
    def cached_keys(self) -> list[str]:
        return list(self._keys)

    # ── Core API ─────────────────────────────────────────────────────────

    async def get_or_compute(
        self,
        key: str,
        ttl: int | None = None,
        func: Callable[[], Awaitable[T]] | Callable[[], T] | None = None,
    ) -> T | None:
        """Return the cached value for ``key`` or compute it via ``func``.

        Lookup order: L1 (memory) -> L2 (Redis) -> L3 (``func``).  When the
        value is computed it is written to L1 (always) and L2 (if Redis is
        reachable).  ``ttl`` defaults to the manager default (seconds).
        """
        ttl = ttl if ttl is not None else self._default_ttl

        # L1 — memory.
        # NOTE: cached ``None`` payloads are treated as misses (recomputed on
        # every call). Use a sentinel object if ``None`` is a meaningful value.
        hit = self._l1.get(key)
        if hit is not None:
            return hit

        # L2 — Redis
        if await self._ensure_redis():
            try:
                raw = await self._redis.get(self._namespaced(key))
                if raw is not None:
                    value = self._deserialize(raw)
                    if value is not None:
                        self._l1.put(key, value)
                        return value
            except Exception:
                logger.warning("CacheManager L2 read failed for %s", key, exc_info=True)

        # L3 — compute (DB fallback)
        if func is None:
            return None
        value = await func() if asyncio.iscoroutinefunction(func) else func()

        # Promote back to L1 + L2
        self._l1.put(key, value)
        if await self._ensure_redis():
            try:
                await self._redis.setex(
                    self._namespaced(key), ttl, self._serialize(value)
                )
                self._keys.add(key)
            except Exception:
                logger.warning("CacheManager L2 write failed for %s", key, exc_info=True)
        return value

    async def get(self, key: str) -> Any | None:
        """Read without computing. Returns None on miss."""
        return await self.get_or_compute(key, ttl=None, func=None)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Write a value into L1 + L2."""
        ttl = ttl if ttl is not None else self._default_ttl
        self._l1.put(key, value)
        if await self._ensure_redis():
            try:
                await self._redis.setex(
                    self._namespaced(key), ttl, self._serialize(value)
                )
                self._keys.add(key)
            except Exception:
                logger.warning("CacheManager L2 write failed for %s", key, exc_info=True)

    async def invalidate(self, key: str) -> None:
        """Evict a key from all layers (memory + Redis)."""
        self._l1.delete(key)
        self._keys.discard(key)
        if self._redis is not None:
            try:
                await self._redis.delete(self._namespaced(key))
            except Exception:
                pass

    async def clear_all(self) -> None:
        """Clear the memory layer and every key this manager has written."""
        self._l1.clear()
        keys = list(self._keys)
        self._keys.clear()
        if self._redis is not None and keys:
            try:
                await self._redis.delete(*[self._namespaced(k) for k in keys])
            except Exception:
                pass

    # ── Serialization ────────────────────────────────────────────────────

    def _namespaced(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    def _serialize(self, value: Any) -> bytes:
        return pickle.dumps(value)

    def _deserialize(self, raw: bytes) -> Any:
        try:
            return pickle.loads(raw)
        except Exception:
            return raw  # non-pickle payload — return as-is


_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """Return the process-wide CacheManager singleton."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(
            redis_url=settings.redis_url,
            max_memory_items=100,
            default_ttl=settings.redis_default_ttl,
        )
    return _cache_manager


def set_cache_manager(manager: CacheManager | None) -> None:
    """Replace the singleton (used by tests / app teardown)."""
    global _cache_manager
    _cache_manager = manager
