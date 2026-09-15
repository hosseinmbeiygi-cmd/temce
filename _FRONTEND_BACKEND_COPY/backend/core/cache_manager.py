"""3-layer cache manager (L1 memory LRU + L2 Redis + L3 compute fallback).

Implements the ``CacheManager`` described in the platform upgrade plan:

* **L1 — memory**: thread-of-execution safe OrderedDict LRU (fast path).
* **L2 — Redis**: shared across workers/processes, TTL-based, JSON payloads.
* **L3 — compute**: when neither L1 nor L2 has the value, ``func()`` is
  awaited (typically a database read) and the result is promoted back to
  both L1 and L2.  Concurrent misses on the same key are collapsed into a
  single ``func()`` call via a Redis ``SET NX`` lock (single-flight), so a
  cold key cannot stampede the database.  If Redis is unavailable the
  manager degrades gracefully to L1-only caching — the value is still
  returned, just not shared.

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
import contextlib
import inspect
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import orjson

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Single-flight lock settings for the L3 compute path.
_LOCK_TTL_SECONDS = 30
_LOCK_WAIT_STEP = 0.1
_LOCK_WAIT_ATTEMPTS = 50  # 50 * 0.1s = 5s max wait for the winner's write


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
            try:
                await self._redis.ping()
                return True
            except Exception:
                self._redis = None
                self._redis_connected = None
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
            with contextlib.suppress(Exception):
                await self._redis.close()
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

        Concurrent misses are single-flighted: the first caller takes a Redis
        ``SET NX`` lock and runs ``func``; the others poll L2 for up to 5s and
        return the winner's value.  A loser that times out falls through and
        computes for itself rather than failing.
        """
        ttl = ttl if ttl is not None else self._default_ttl

        # L1 — memory.
        # NOTE: cached ``None`` payloads are treated as misses (recomputed on
        # every call). Use a sentinel object if ``None`` is a meaningful value.
        hit = self._l1.get(key)
        if hit is not None:
            return hit

        # L2 — Redis
        cached = await self._read_l2(key)
        if cached is not None:
            self._l1.put(key, cached)
            return cached

        # L3 — compute (DB fallback)
        if func is None:
            return None

        # Single-flight: only the lock winner computes.
        lock_key = self._namespaced(f"lock:{key}")
        holds_lock = False
        if await self._ensure_redis():
            try:
                holds_lock = bool(await self._redis.set(lock_key, b"1", nx=True, ex=_LOCK_TTL_SECONDS))
            except Exception:
                logger.warning("CacheManager lock failed for %s", key, exc_info=True)
                holds_lock = True  # fail open — compute rather than hang
            if not holds_lock:
                waited = await self._await_winner(key)
                if waited is not None:
                    self._l1.put(key, waited)
                    return waited
                logger.warning("CacheManager single-flight wait timed out for %s", key)

        try:
            maybe = func()
            value = await maybe if inspect.isawaitable(maybe) else maybe
        finally:
            if holds_lock and self._redis is not None:
                with contextlib.suppress(Exception):
                    await self._redis.delete(lock_key)

        # Promote back to L1 + L2
        self._l1.put(key, value)
        await self._write_l2(key, value, ttl)
        return value

    async def _read_l2(self, key: str) -> Any | None:
        """Read a single key from Redis. Returns None on miss or any error."""
        if not await self._ensure_redis():
            return None
        try:
            raw = await self._redis.get(self._namespaced(key))
        except Exception:
            logger.warning("CacheManager L2 read failed for %s", key, exc_info=True)
            self._redis = None
            self._redis_connected = None
            return None
        return self._deserialize(raw) if raw is not None else None

    async def _write_l2(self, key: str, value: Any, ttl: int) -> None:
        """Write a value to Redis under ``ttl``. Never raises."""
        if not await self._ensure_redis():
            return
        try:
            payload = self._serialize(value)
        except TypeError:
            logger.warning("CacheManager: %s is not JSON-serialisable, L1-only", key, exc_info=True)
            return
        try:
            await self._redis.setex(self._namespaced(key), ttl, payload)
            self._keys.add(key)
        except Exception:
            logger.warning("CacheManager L2 write failed for %s", key, exc_info=True)
            self._redis = None
            self._redis_connected = None

    async def _await_winner(self, key: str) -> Any | None:
        """Poll L2 for the lock winner's write. Returns None if it never lands."""
        for _ in range(_LOCK_WAIT_ATTEMPTS):
            await asyncio.sleep(_LOCK_WAIT_STEP)
            value = await self._read_l2(key)
            if value is not None:
                return value
        return None

    async def get(self, key: str) -> Any | None:
        """Read without computing. Returns None on miss."""
        return await self.get_or_compute(key, ttl=None, func=None)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Write a value into L1 + L2."""
        ttl = ttl if ttl is not None else self._default_ttl
        self._l1.put(key, value)
        await self._write_l2(key, value, ttl)

    async def invalidate(self, key: str) -> None:
        """Evict a key from all layers (memory + Redis)."""
        self._l1.delete(key)
        self._keys.discard(key)
        if self._redis is not None:
            try:
                await self._redis.delete(self._namespaced(key))
            except Exception:
                logger.warning(
                    "CacheManager L2 invalidate failed for %s — stale value may be served by other workers",
                    key,
                    exc_info=True,
                )

    async def clear_all(self) -> None:
        """Clear the memory layer and every key this manager has written."""
        self._l1.clear()
        keys = list(self._keys)
        self._keys.clear()
        if self._redis is not None and keys:
            try:
                await self._redis.delete(*[self._namespaced(k) for k in keys])
            except Exception:
                logger.warning(
                    "CacheManager L2 clear_all failed (%d keys) — stale values may be served by other workers",
                    len(keys),
                    exc_info=True,
                )

    # ── Serialization ────────────────────────────────────────────────────

    def _namespaced(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    def _serialize(self, value: Any) -> bytes:
        """JSON-encode a value. Raises TypeError on unsupported types.

        Deliberately not pickle: L2 payloads are attacker-reachable for anyone
        with write access to the Redis keyspace, and ``pickle.loads`` on such a
        payload is arbitrary code execution in this process.
        """
        return orjson.dumps(value, option=orjson.OPT_SERIALIZE_NUMPY)

    def _deserialize(self, raw: bytes) -> Any:
        try:
            return orjson.loads(raw)
        except orjson.JSONDecodeError:
            logger.warning("CacheManager: dropped non-JSON L2 payload")
            return None


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
