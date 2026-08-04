from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any, TypeVar

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class NullCache:
    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def pop(self, key: str) -> Any | None:
        """Atomically return and remove a key (no-op for the null cache)."""
        return None

    async def remember(self, key: str, ttl: int, factory: Callable[[], T]) -> T:
        return await factory() if asyncio.iscoroutinefunction(factory) else factory()


class CacheService:
    def __init__(self, redis_url: str | None = None, default_ttl: int = 300) -> None:
        self._default_ttl = default_ttl
        self._redis: Any = None
        self._redis_url = redis_url or settings.redis_url
        self._null_cache = NullCache()

    async def initialize(self) -> None:
        # Idempotent: never create a second connection when already connected.
        # This makes initialize() safe to call from multiple places (app
        # lifespan, scheduler, RedisClient facade, health checks). After a
        # close() the client is None again, so reconnect still works.
        # Note: if the live connection drops (e.g. Redis restart) initialize()
        # will not re-create it — use ping() as the liveness check.
        if self._redis is not None:
            return
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
            await self._redis.ping()
            logger.info("Connected to Redis at %s", self._redis_url)
        except Exception:
            logger.warning("Redis unavailable, using null cache")
            self._redis = None

    @property
    def is_connected(self) -> bool:
        """Return True if Redis is connected and reachable."""
        return self._redis is not None

    @property
    def client(self) -> Any | None:
        """Raw redis.asyncio client, or None when Redis is unavailable.

        Used by distributed components (e.g. JobLocking) that need direct
        access to SET NX PX / Lua primitives rather than the serialized
        get/set helpers.
        """
        return self._redis

    async def ping(self) -> bool:
        """Ping Redis. Returns True if reachable, False otherwise."""
        if self._redis is None:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    def _serialize(self, value: Any) -> str:
        return json.dumps(value, default=str)

    def _deserialize(self, value: str | None) -> Any | None:
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def get(self, key: str) -> Any | None:
        if self._redis is None:
            return await self._null_cache.get(key)
        val = await self._redis.get(key)
        return self._deserialize(val)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if self._redis is None:
            return
        ttl = ttl if ttl is not None else self._default_ttl
        serialized = self._serialize(value)
        await self._redis.setex(key, ttl, serialized)

    async def set_persistent(self, key: str, value: Any) -> None:
        """Set a key with no expiry.

        Used for durable shared state (e.g. the orchestrator cron state)
        that must survive the default TTL and be visible across workers.
        """
        if self._redis is None:
            return
        await self._redis.set(key, self._serialize(value))

    async def delete(self, key: str) -> None:
        if self._redis is None:
            return
        await self._redis.delete(key)

    async def pop(self, key: str) -> Any | None:
        """Atomically return and delete a key (single-use tokens, leases).

        Uses ``GETDEL`` (Redis 6.2+) so concurrent consumers can never both
        read the same value — exactly one caller gets it. Falls back to a
        plain get+delete for compatibility with older servers.
        """
        if self._redis is None:
            return None
        try:
            val = await self._redis.getdel(key)
        except Exception:  # noqa: BLE001 — server may not support GETDEL
            val = await self._redis.get(key)
            if val is not None:
                await self._redis.delete(key)
        return self._deserialize(val)

    async def remember(self, key: str, ttl: int, factory: Callable[[], T]) -> T:
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
        await self.set(key, value, ttl)
        return value


_cache_instance: CacheService | None = None


def get_cache() -> CacheService:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService(
            redis_url=settings.redis_url,
            default_ttl=settings.redis_default_ttl,
        )
    return _cache_instance
