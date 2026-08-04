from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """Compatibility facade over the shared :class:`core.cache.CacheService`.

    Item 15 (Duplicate Cache) unification: the app owns a single Redis
    connection via ``get_cache()`` (initialized in the API/scheduler
    lifespan). ``RedisClient`` no longer opens a second connection — every
    method delegates to the shared raw client, so there is exactly one
    Redis connection per process.

    When a *custom* ``url`` is supplied (different from ``REDIS_URL``) a
    private self-managed connection is used instead (legacy behaviour), so
    callers pointing at another Redis keep working unchanged.

    For the default URL an explicit ``connect()`` is not strictly required:
    if the app lifespan already initialized the shared cache, methods act on
    it immediately. ``connect()`` is best-effort and never raises (it
    delegates to ``initialize()`` which swallows errors) — use ``ping()`` to
    detect whether Redis is actually reachable.

    All graceful no-op fallbacks are preserved: when Redis is unavailable
    the methods return ``None``/``False``/empty collections instead of
    raising.
    """

    def __init__(self, url: str | None = None):
        self._url = url or settings.redis_url
        # Private connection — only used when a custom URL is supplied.
        self._own_client: aioredis.Redis | None = None

    @staticmethod
    def _shared():
        # Lazy import so tests patching core.cache.get_cache take effect and
        # there is no import cycle (core.cache never imports integrations).
        from core.cache import get_cache

        return get_cache()

    @property
    def _client(self) -> Any | None:
        if self._own_client is not None:
            return self._own_client
        return self._shared().client

    async def connect(self) -> None:
        if self._own_client is not None:
            return
        if self._url != settings.redis_url:
            # Custom URL → manage a private connection (legacy behaviour).
            self._own_client = aioredis.from_url(self._url, decode_responses=True)
            await self._own_client.ping()
            logger.info("Connected to Redis at %s", self._url)
        else:
            # Default URL → reuse the app-wide shared connection.
            # Best-effort: initialize() never raises (falls back to null cache).
            await self._shared().initialize()

    async def disconnect(self) -> None:
        if self._own_client is not None:
            await self._own_client.close()
            self._own_client = None
        # The shared connection is owned by the app lifespan — never close it.

    async def ping(self) -> bool:
        if self._own_client is not None:
            try:
                await self._own_client.ping()
                return True
            except Exception:
                return False
        return await self._shared().ping()

    async def get(self, key: str) -> Any | None:
        client = self._client
        if client is None:
            return None
        val = await client.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        client = self._client
        if client is None:
            return
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        if ttl is not None:
            await client.setex(key, ttl, serialized)
        else:
            await client.set(key, serialized)

    async def delete(self, key: str) -> bool:
        client = self._client
        if client is None:
            return False
        return bool(await client.delete(key))

    async def exists(self, key: str) -> bool:
        client = self._client
        if client is None:
            return False
        return bool(await client.exists(key))

    async def expire(self, key: str, ttl: int) -> bool:
        client = self._client
        if client is None:
            return False
        return bool(await client.expire(key, ttl))

    async def ttl(self, key: str) -> int:
        client = self._client
        if client is None:
            return -2
        return await client.ttl(key)

    async def keys(self, pattern: str = "*") -> list[str]:
        client = self._client
        if client is None:
            return []
        return list(await client.keys(pattern))

    async def incr(self, key: str, amount: int = 1) -> int:
        client = self._client
        if client is None:
            return 0
        return await client.incr(key, amount)

    async def sadd(self, key: str, *values: str) -> int:
        client = self._client
        if client is None:
            return 0
        return await client.sadd(key, *values)

    async def srem(self, key: str, *values: str) -> int:
        client = self._client
        if client is None:
            return 0
        return await client.srem(key, *values)

    async def smembers(self, key: str) -> set[str]:
        client = self._client
        if client is None:
            return set()
        return set(await client.smembers(key))

    async def publish(self, channel: str, message: Any) -> int:
        client = self._client
        if client is None:
            return 0
        serialized = json.dumps(message, ensure_ascii=False, default=str)
        return await client.publish(channel, serialized)

    async def clear(self) -> None:
        client = self._client
        if client is None:
            return
        await client.flushdb()

    @property
    def client(self) -> aioredis.Redis | None:
        return self._client
