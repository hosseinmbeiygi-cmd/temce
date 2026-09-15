from __future__ import annotations

import json
import time
from typing import Any


class MarketDataCache:
    """Redis-backed cache with an in-process fallback.

    A Redis outage must not stop ingestion; callers receive a cache miss and the
    next successful fetch repopulates the cache.
    """

    def __init__(self, redis_client: Any | None = None, *, namespace: str = "antigravity:market") -> None:
        self._redis = redis_client
        self._namespace = namespace
        self._memory: dict[str, tuple[float, bytes]] = {}

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    async def get_json(self, key: str) -> Any | None:
        namespaced = self._key(key)
        try:
            if self._redis is not None:
                value = await self._redis.get(namespaced)
                if value is not None:
                    return json.loads(value)
        except Exception:
            pass
        cached = self._memory.get(namespaced)
        if cached and cached[0] > time.monotonic():
            return json.loads(cached[1])
        self._memory.pop(namespaced, None)
        return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        namespaced = self._key(key)
        payload = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        try:
            if self._redis is not None:
                await self._redis.setex(namespaced, ttl_seconds, payload)
        except Exception:
            pass
        self._memory[namespaced] = (time.monotonic() + ttl_seconds, payload)

    async def delete(self, key: str) -> None:
        namespaced = self._key(key)
        try:
            if self._redis is not None:
                await self._redis.delete(namespaced)
        except Exception:
            pass
        self._memory.pop(namespaced, None)
