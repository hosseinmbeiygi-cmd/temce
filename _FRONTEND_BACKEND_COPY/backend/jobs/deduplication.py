from __future__ import annotations

import time

from core.logging import get_logger

logger = get_logger(__name__)


class JobDeduplicator:
    def __init__(self, ttl: float = 3600.0):
        self._store: dict[str, float] = {}
        self._ttl = ttl

    async def is_duplicate(self, key: str) -> bool:
        self._purge_expired()
        return key in self._store

    async def mark(self, key: str, ttl: float | None = None) -> None:
        self._store[key] = time.monotonic() + (ttl or self._ttl)

    async def remove(self, key: str) -> None:
        self._store.pop(key, None)

    async def clear(self) -> None:
        self._store.clear()

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, expires in self._store.items() if now >= expires]
        for k in expired:
            del self._store[k]
