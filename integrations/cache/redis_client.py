from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    def __init__(self, url: str | None = None):
        self._url = url or settings.redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        if self._client is None:
            self._client = aioredis.from_url(self._url, decode_responses=True)
            await self._client.ping()
            logger.info("Connected to Redis at %s", self._url)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Any | None:
        if not self._client:
            return None
        val = await self._client.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        if not self._client:
            return
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        if ttl is not None:
            await self._client.setex(key, ttl, serialized)
        else:
            await self._client.set(key, serialized)

    async def delete(self, key: str) -> bool:
        if not self._client:
            return False
        return bool(await self._client.delete(key))

    async def exists(self, key: str) -> bool:
        if not self._client:
            return False
        return bool(await self._client.exists(key))

    async def expire(self, key: str, ttl: int) -> bool:
        if not self._client:
            return False
        return bool(await self._client.expire(key, ttl))

    async def ttl(self, key: str) -> int:
        if not self._client:
            return -2
        return await self._client.ttl(key)

    async def keys(self, pattern: str = "*") -> list[str]:
        if not self._client:
            return []
        return list(await self._client.keys(pattern))

    async def incr(self, key: str, amount: int = 1) -> int:
        if not self._client:
            return 0
        return await self._client.incr(key, amount)

    async def sadd(self, key: str, *values: str) -> int:
        if not self._client:
            return 0
        return await self._client.sadd(key, *values)

    async def srem(self, key: str, *values: str) -> int:
        if not self._client:
            return 0
        return await self._client.srem(key, *values)

    async def smembers(self, key: str) -> set[str]:
        if not self._client:
            return set()
        return set(await self._client.smembers(key))

    async def publish(self, channel: str, message: Any) -> int:
        if not self._client:
            return 0
        serialized = json.dumps(message, ensure_ascii=False, default=str)
        return await self._client.publish(channel, serialized)

    async def clear(self) -> None:
        if not self._client:
            return
        await self._client.flushdb()

    @property
    def client(self) -> aioredis.Redis | None:
        return self._client
