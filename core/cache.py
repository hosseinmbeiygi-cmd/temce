from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import Callable
from typing import Any, TypeVar, cast

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
    #: Without these the redis client waits far longer than any HTTP request
    #: budget when a connection goes bad (defaults are seconds, not fractions).
    socket_timeout: float = 0.3
    #: First TCP connect attempt. On Windows ``localhost`` resolves to ``::1``
    #: before ``127.0.0.1``, and the refused IPv6 attempt alone can burn ~2 s,
    #: so a 0.3 s budget is retried once with :attr:`socket_connect_timeout_fallback`
    #: instead of leaving Redis permanently disabled.
    socket_connect_timeout: float = 0.3
    socket_connect_timeout_fallback: float = 2.5
    #: After a failure, stop calling Redis at all for this long. One dead
    #: connection otherwise costs every caller the full socket timeout.
    breaker_seconds: float = 30.0

    def __init__(self, redis_url: str | None = None, default_ttl: int = 300) -> None:
        self._default_ttl = default_ttl
        self._redis: Any = None
        self._redis_url = redis_url or settings.redis_url
        self._null_cache = NullCache()
        #: Event loop the client was created on. redis.asyncio transports are
        #: bound to it; awaiting them from another (later) loop raises
        #: ``RuntimeError: Event loop is closed``.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._unavailable_until: float = 0.0

    async def initialize(self) -> None:
        # Idempotent: never create a second connection when already connected.
        # This makes initialize() safe to call from multiple places (app
        # lifespan, scheduler, RedisClient facade, health checks). After a
        # close() the client is None again, so reconnect still works.
        # Note: if the live connection drops (e.g. Redis restart) initialize()
        # will not re-create it — use ping() as the liveness check.
        if self._redis is not None:
            loop = self._running_loop()
            if loop is None or self._loop is None or loop is self._loop:
                return
            # Client from a previous loop: start over on this one.
            self.reset()
        from redis.asyncio import from_url
        from redis.asyncio.retry import Retry
        from redis.backoff import NoBackoff

        last_exc: BaseException | None = None
        for connect_timeout in (
            self.socket_connect_timeout,
            self.socket_connect_timeout_fallback,
        ):
            # ``redis.asyncio.from_url`` ships without type hints.
            client = cast(Any, from_url)(
                self._redis_url,
                decode_responses=True,
                # One attempt only: rate limiting and token revocation both
                # have local fallbacks, so retrying is worse than failing fast.
                retry=Retry(NoBackoff(), 1),
                retry_on_error=[],
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=connect_timeout,
                health_check_interval=0,
            )
            try:
                await client.ping()
            except Exception as exc:  # noqa: BLE001 — try the wider budget
                last_exc = exc
                # Failed connect: nothing to drain.
                with contextlib.suppress(Exception):
                    await client.aclose()
                continue
            self._redis = client
            self._loop = asyncio.get_running_loop()
            self._unavailable_until = 0.0
            logger.info("Connected to Redis at %s", self._redis_url)
            return

        logger.warning("Redis unavailable, using null cache: %s", last_exc)
        self._redis = None
        self._loop = None

    def reset(self) -> None:
        """Detach the client without awaiting it.

        Safe to call from a *different* event loop than the one that created
        the client (``close()`` is not: awaiting a transport bound to a closed
        loop is exactly what hangs). The old socket is left for the garbage
        collector; a later ``initialize()`` creates a fresh client on the
        current loop.
        """
        self._redis = None
        self._loop = None
        self._unavailable_until = 0.0

    @staticmethod
    def _running_loop() -> asyncio.AbstractEventLoop | None:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def _record_failure(self, exc: BaseException) -> None:
        self._unavailable_until = time.monotonic() + self.breaker_seconds
        logger.warning(
            "Redis disabled for %.0fs after %s: %s",
            self.breaker_seconds,
            type(exc).__name__,
            exc,
        )

    def _client(self) -> Any | None:
        """Return the client only when it is safe to await right now."""
        if self._redis is None:
            return None
        if time.monotonic() < self._unavailable_until:
            return None
        loop = self._running_loop()
        if loop is not None and self._loop is not None and loop is not self._loop:
            # The client belongs to a previous (closed) loop — pytest creates
            # one loop per test. Reusing it raises "Event loop is closed"
            # after a multi-second stall, so detach and fall back instead.
            logger.debug("Redis client belongs to a stale event loop; detaching")
            self.reset()
            return None
        return self._redis

    @property
    def is_connected(self) -> bool:
        """True only when the client exists, no breaker is open and the loop matches."""
        return self._client() is not None

    @property
    def client(self) -> Any | None:
        """Raw redis.asyncio client, or None when Redis cannot be used.

        Used by distributed components (e.g. JobLocking) that need direct
        access to SET NX PX / Lua primitives rather than the serialized
        get/set helpers. Breaker- and loop-aware, so callers get ``None``
        instead of a client that will hang.
        """
        return self._client()

    async def ping(self) -> bool:
        """Ping Redis. Returns True if reachable, False otherwise."""
        client = self._client()
        if client is None:
            return False
        try:
            await client.ping()
            return True
        except Exception as exc:  # noqa: BLE001 — liveness check
            self._record_failure(exc)
            return False

    async def close(self) -> None:
        if self._redis is not None:
            # Already-closed loop/transport must not raise on shutdown.
            with contextlib.suppress(Exception):
                await self._redis.aclose()
        self.reset()

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
        client = self._client()
        if client is None:
            return await self._null_cache.get(key)
        try:
            val = await client.get(key)
        except Exception as exc:  # noqa: BLE001 — cache must never break a request
            self._record_failure(exc)
            return None
        return self._deserialize(val)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        client = self._client()
        if client is None:
            return
        ttl = ttl if ttl is not None else self._default_ttl
        serialized = self._serialize(value)
        try:
            await client.setex(key, ttl, serialized)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(exc)

    async def set_persistent(self, key: str, value: Any) -> None:
        """Set a key with no expiry.

        Used for durable shared state (e.g. the orchestrator cron state)
        that must survive the default TTL and be visible across workers.
        """
        client = self._client()
        if client is None:
            return
        try:
            await client.set(key, self._serialize(value))
        except Exception as exc:  # noqa: BLE001
            self._record_failure(exc)

    async def delete(self, key: str) -> None:
        client = self._client()
        if client is None:
            return
        try:
            await client.delete(key)
        except Exception as exc:  # noqa: BLE001
            self._record_failure(exc)

    async def pop(self, key: str) -> Any | None:
        """Atomically return and delete a key (single-use tokens, leases).

        Uses ``GETDEL`` (Redis 6.2+) so concurrent consumers can never both
        read the same value — exactly one caller gets it. Falls back to a
        plain get+delete for compatibility with older servers.
        """
        client = self._client()
        if client is None:
            return None
        try:
            val = await client.getdel(key)
        except Exception:  # noqa: BLE001 — server may not support GETDEL
            try:
                val = await client.get(key)
                if val is not None:
                    await client.delete(key)
            except Exception as exc:  # noqa: BLE001
                self._record_failure(exc)
                return None
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


def reset_cache() -> None:
    """Drop the process-wide cache singleton (tests only).

    Unit tests each run on a fresh event loop, so a client created by an
    earlier test is unusable: it must never be carried across the boundary.
    """
    global _cache_instance
    if _cache_instance is not None:
        _cache_instance.reset()
    _cache_instance = None
