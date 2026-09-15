from __future__ import annotations

import asyncio
import time
from typing import Any

from core.cache import get_cache
from core.logging import get_logger

logger = get_logger(__name__)

# Atomic compare-and-delete: only the lock owner may release it.
_LUA_RELEASE = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# Atomic compare-and-extend: only the lock owner may renew the TTL.
_LUA_EXTEND = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""


class JobLocking:
    """Distributed job lock shared across workers/processes.

    Primary backend is Redis using ``SET key owner NX PX <ttl_ms>`` so the
    lock auto-expires (a crashed worker never leaves a stuck lock) and only
    the owning worker can release/extend it (Lua compare-and-{del,pexpire}).

    When Redis is unavailable the class degrades to an in-memory lock with
    identical semantics to the previous single-process implementation, so
    existing callers and tests keep working unchanged.
    """

    def __init__(self, default_ttl: float = 300.0):
        self._default_ttl = default_ttl
        # In-memory fallback (used only when Redis is unavailable)
        self._locks: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    # ── Redis plumbing ────────────────────────────────────────────────

    def _redis(self) -> Any | None:
        """Return the connected redis client, or None (use in-memory fallback)."""
        try:
            client = get_cache().client
        except Exception:
            client = None
        return client

    async def _acquire_redis(self, key: str, owner: str, ttl: float) -> bool:
        client = self._redis()
        if client is None:
            return False
        try:
            return bool(await client.set(key, owner, nx=True, px=int(ttl * 1000)))
        except Exception as e:
            logger.debug("Redis lock acquire failed for %s: %s", key, e)
            return False

    async def _release_redis(self, key: str, owner: str) -> bool:
        client = self._redis()
        if client is None:
            return False
        try:
            return bool(await client.eval(_LUA_RELEASE, 1, key, owner))
        except Exception as e:
            logger.debug("Redis lock release failed for %s: %s", key, e)
            return False

    async def _extend_redis(self, key: str, owner: str, ttl: float) -> bool:
        client = self._redis()
        if client is None:
            return False
        try:
            return bool(await client.eval(_LUA_EXTEND, 1, key, owner, int(ttl * 1000)))
        except Exception as e:
            logger.debug("Redis lock extend failed for %s: %s", key, e)
            return False

    async def _is_locked_redis(self, key: str) -> bool:
        client = self._redis()
        if client is None:
            return False
        try:
            return bool(await client.exists(key))
        except Exception as e:
            logger.debug("Redis lock exists failed for %s: %s", key, e)
            return False

    async def _get_owner_redis(self, key: str) -> str | None:
        client = self._redis()
        if client is None:
            return None
        try:
            return await client.get(key)
        except Exception as e:
            logger.debug("Redis lock get failed for %s: %s", key, e)
            return None

    # ── Public API ────────────────────────────────────────────────────

    async def acquire(self, key: str, owner: str, ttl: float | None = None) -> bool:
        ttl = ttl or self._default_ttl
        # Redis path: SET NX PX is atomic — failure means another worker
        # holds the lock (or a Redis error). Fail closed: do not run twice.
        if self._redis() is not None:
            return await self._acquire_redis(key, owner, ttl)
        # In-memory fallback
        async with self._lock:
            existing = self._locks.get(key)
            if existing is not None:
                existing_owner, expires_at = existing
                if time.monotonic() < expires_at and existing_owner != owner:
                    return False
            self._locks[key] = (owner, time.monotonic() + ttl)
            return True

    async def release(self, key: str, owner: str) -> bool:
        if self._redis() is not None:
            if await self._release_redis(key, owner):
                return True
            # Nothing to release (already gone) == success, matching the
            # in-memory semantics; a token mismatch means someone else owns it.
            return not await self._is_locked_redis(key)
        async with self._lock:
            existing = self._locks.get(key)
            if existing is None:
                return True
            if existing[0] != owner:
                return False
            del self._locks[key]
            return True

    async def is_locked(self, key: str) -> bool:
        if self._redis() is not None:
            return await self._is_locked_redis(key)
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
        if self._redis() is not None:
            return await self._extend_redis(key, owner, ttl)
        async with self._lock:
            existing = self._locks.get(key)
            if existing is None or existing[0] != owner:
                return False
            self._locks[key] = (owner, time.monotonic() + ttl)
            return True

    async def clear(self) -> None:
        # Only the in-memory fallback is cleared; Redis keys are released
        # individually via release() so we never delete another worker's lock.
        async with self._lock:
            self._locks.clear()

    async def get_owner(self, key: str) -> str | None:
        if self._redis() is not None:
            return await self._get_owner_redis(key)
        async with self._lock:
            existing = self._locks.get(key)
            if existing:
                owner, expires_at = existing
                if time.monotonic() < expires_at:
                    return owner
                del self._locks[key]
            return None

    async def purge_expired(self) -> int:
        # Redis keys expire automatically; purge only the in-memory fallback.
        async with self._lock:
            now = time.monotonic()
            expired = [k for k, (_, expires_at) in self._locks.items() if now >= expires_at]
            for k in expired:
                del self._locks[k]
            return len(expired)


class RedisJobLock(JobLocking):
    """Design-doc-compatible facade over :class:`JobLocking`.

    The original architecture sketch (``ANALYSIS.md``) used the simpler
    signature ``acquire(job_name, ttl)`` without an explicit owner token.
    This class provides that API while keeping the stronger owner-safe
    semantics of :class:`JobLocking`: a per-instance owner token is generated
    automatically, so ``release()`` / ``extend()`` only ever affect locks this
    instance actually holds.

    Usage::

        lock = RedisJobLock(ttl=300)
        if await lock.acquire("sync_quotes"):
            try:
                ...  # run the job
            finally:
                await lock.release("sync_quotes")
        else:
            # another worker is already running it
            pass
    """

    def __init__(self, ttl: int = 300) -> None:
        super().__init__(default_ttl=float(ttl))
        import uuid

        self._owner = f"redisjoblock-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _key(job_name: str) -> str:
        return f"job:{job_name}"

    async def acquire(self, job_name: str, ttl: int | None = None) -> bool:
        """Acquire the distributed lock for *job_name* (SET NX PX).

        Returns ``True`` when this instance got the lock, ``False`` when
        another worker holds it (or Redis is unreachable and the in-memory
        fallback is also taken).
        """
        return await super().acquire(self._key(job_name), self._owner, ttl)

    async def release(self, job_name: str) -> bool:
        """Release the lock — only succeeds when this instance owns it."""
        return await super().release(self._key(job_name), self._owner)

    async def extend(self, job_name: str, ttl: int = 300) -> bool:
        """Renew the TTL — only succeeds when this instance owns the lock."""
        return await super().extend(self._key(job_name), self._owner, float(ttl))

    async def is_locked(self, job_name: str) -> bool:
        """Return whether *job_name* is currently locked by any worker."""
        return await super().is_locked(self._key(job_name))
