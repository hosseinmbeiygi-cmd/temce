from __future__ import annotations

import json
from typing import Any

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class CacheManager:
    def __init__(self, redis_url: str = "") -> None:
        self.redis_url = redis_url or settings.redis_url
        self._client: Any = None
        self._local_cache: dict[str, tuple[Any, float]] = {}
        self._enabled = True

    async def _get_client(self) -> Any:
        if self._client is None:
            try:
                import redis.asyncio as aioredis

                self._client = aioredis.from_url(self.redis_url, decode_responses=True)
            except Exception as e:
                logger.warning("Redis unavailable, using local cache: %s", e)
                self._enabled = False
        return self._client

    async def get(self, key: str) -> Any | None:
        if not self._enabled:
            return self._local_cache.get(key, (None, 0))[0]
        try:
            client = await self._get_client()
            val = await client.get(key)
            return json.loads(val) if val else None
        except Exception:
            return self._local_cache.get(key, (None, 0))[0]

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if not self._enabled:
            self._local_cache[key] = (value, ttl)
            return
        try:
            client = await self._get_client()
            await client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning("Cache set failed: %s", e)

    async def delete(self, key: str) -> None:
        if not self._enabled:
            self._local_cache.pop(key, None)
            return
        try:
            client = await self._get_client()
            await client.delete(key)
        except Exception as e:
            logger.warning("Cache delete failed: %s", e)

    async def close(self) -> None:
        if self._client:
            await self._client.close()


cache_manager = CacheManager()
