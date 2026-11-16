from __future__ import annotations

import contextlib
import json
import time
from typing import Any


class MarketDataCache:
    """Redis-backed cache with an in-process fallback.

    A Redis outage must not stop ingestion; callers receive a cache miss and the
    next successful fetch repopulates the cache.

    ING-10: ``_memory`` is bounded to ``_MAX_MEMORY_ENTRIES`` entries.  When
    Redis is healthy every ``set_json`` also writes to Redis; the in-process
    dict is only used as a Redis-down fallback, so the entry count stays small
    in practice.  The cap prevents unbounded growth during extended Redis
    outages.  Eviction policy: drop the oldest entry (insertion-order dict).
    """

    # ING-10: cap the in-process fallback to avoid unbounded memory growth.
    _MAX_MEMORY_ENTRIES: int = 500

    def __init__(self, redis_client: Any | None = None, *, namespace: str = "market") -> None:
        self._redis = redis_client
        # ING-10: "antigravity:market" was the old hardcoded default namespace —
        # renamed to the generic "market" so the class is reusable across
        # services without the domain-specific prefix leaking into key names.
        self._namespace = namespace
        self._memory: dict[str, tuple[float, bytes]] = {}

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    async def get_json(self, key: str) -> Any | None:
        namespaced = self._key(key)
        with contextlib.suppress(Exception):
            if self._redis is not None:
                value = await self._redis.get(namespaced)
                if value is not None:
                    return json.loads(value)
        cached = self._memory.get(namespaced)
        if cached and cached[0] > time.monotonic():
            return json.loads(cached[1])
        self._memory.pop(namespaced, None)
        return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        namespaced = self._key(key)
        payload = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        with contextlib.suppress(Exception):
            if self._redis is not None:
                await self._redis.setex(namespaced, ttl_seconds, payload)
        # ING-10: evict the oldest entry when at capacity.
        if len(self._memory) >= self._MAX_MEMORY_ENTRIES and namespaced not in self._memory:
            self._memory.pop(next(iter(self._memory)), None)
        self._memory[namespaced] = (time.monotonic() + ttl_seconds, payload)

    async def delete(self, key: str) -> None:
        namespaced = self._key(key)
        with contextlib.suppress(Exception):
            if self._redis is not None:
                await self._redis.delete(namespaced)
        self._memory.pop(namespaced, None)
