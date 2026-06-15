from __future__ import annotations

import asyncio
import time

from core.logging import get_logger

logger = get_logger(__name__)


class JobLocking:
    def __init__(self, default_ttl: float = 300.0):
        self._locks: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, owner: str, ttl: float | None = None) -> bool:
        ttl = ttl or 300.0
        async with self._lock:
            existing = self._locks.get(key)
            if existing is not None:
                existing_owner, expires_at = existing
                if time.monotonic() < expires_at and existing_owner != owner:
                    return False
            self._locks[key] = (owner, time.monotonic() + ttl)
            return True

    async def release(self, key: str, owner: str) -> bool:
        async with self._lock:
            existing = self._locks.get(key)
            if existing is None:
                return True
            if existing[0] != owner:
                return False
            del self._locks[key]
            return True

    async def is_locked(self, key: str) -> bool:
        async with self._lock:
            existing = self._locks.get(key)
            if existing is None:
                return False
            _, expires_at = existing
            if time.monotonic() >= expires_at:
                del self._locks[key]
                return False
            return True

    async def extend(self, key: str, owner: str, ttl: float = 300.0) -> bool:
        async with self._lock:
            existing = self._locks.get(key)
            if existing is None or existing[0] != owner:
                return False
            self._locks[key] = (owner, time.monotonic() + ttl)
            return True

    async def clear(self) -> None:
        async with self._lock:
            self._locks.clear()

    async def get_owner(self, key: str) -> str | None:
        async with self._lock:
            existing = self._locks.get(key)
            if existing:
                owner, expires_at = existing
                if time.monotonic() < expires_at:
                    return owner
                del self._locks[key]
            return None

    async def purge_expired(self) -> int:
        async with self._lock:
            now = time.monotonic()
            expired = [k for k, (_, expires_at) in self._locks.items() if now >= expires_at]
            for k in expired:
                del self._locks[k]
            return len(expired)
