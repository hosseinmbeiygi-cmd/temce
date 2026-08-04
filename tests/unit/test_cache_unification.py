"""Unit tests for item-15 cache unification.

Verifies that:
  - core.cache.CacheService.initialize() is idempotent (one connection).
  - integrations.cache.RedisClient is a facade over the shared CacheService
    connection (no second connection for the default URL).
  - RedisClient with a custom URL still manages its own private connection.
  - RedisClient keeps its graceful no-op fallbacks when Redis is unavailable.
  - Housekeeping jobs (CacheWarmupJob / HealthCheckJob) use the shared cache.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


# ── Minimal fake redis client (surface used by CacheService/RedisClient) ──


class FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, px: int | None = None) -> bool | None:
        if nx and key in self._data:
            return None
        self._data[key] = value
        return True

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        self._data[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def delete(self, key: str) -> int:
        return 1 if self._data.pop(key, None) is not None else 0

    async def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

    async def expire(self, key: str, ttl: int) -> bool:
        return key in self._data

    async def ttl(self, key: str) -> int:
        return 300 if key in self._data else -2

    async def keys(self, pattern: str = "*") -> list[str]:
        return list(self._data)

    async def incr(self, key: str, amount: int = 1) -> int:
        val = int(self._data.get(key, 0)) + amount
        self._data[key] = str(val)
        return val

    async def sadd(self, key: str, *values: str) -> int:
        s = set(self._data.get(key, "").split(",")) if self._data.get(key) else set()
        before = len(s)
        s.update(values)
        self._data[key] = ",".join(sorted(s))
        return len(s) - before

    async def srem(self, key: str, *values: str) -> int:
        s = set(self._data.get(key, "").split(",")) if self._data.get(key) else set()
        before = len(s)
        s.difference_update(values)
        self._data[key] = ",".join(sorted(s))
        return before - len(s)

    async def smembers(self, key: str) -> set[str]:
        raw = self._data.get(key, "")
        return set(raw.split(",")) if raw else set()

    async def publish(self, channel: str, message: str) -> int:
        return 1

    async def flushdb(self) -> bool:
        self._data.clear()
        return True


class StubCache:
    """CacheService stand-in: exposes .client and the get/set used by jobs."""

    def __init__(self, client, ping_ok: bool = True) -> None:
        self._client = client
        self._ping_ok = ping_ok
        self.initialize_calls = 0

    @property
    def client(self):
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    async def initialize(self) -> None:
        self.initialize_calls += 1

    async def ping(self) -> bool:
        return self._ping_ok

    async def get(self, key: str):
        if self._client is None:
            return None
        raw = await self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(self, key: str, value, ttl: int | None = None) -> None:
        if self._client is None:
            return
        serialized = json.dumps(value, default=str)
        if ttl is not None:
            await self._client.setex(key, ttl, serialized)
        else:
            await self._client.set(key, serialized)


# ── CacheService.initialize() idempotency ────────────────────────────


@pytest.mark.asyncio
async def test_initialize_is_idempotent():
    """initialize() twice must not create a second connection."""
    from core.cache import CacheService

    fake = AsyncMock()
    fake.ping = AsyncMock(return_value=True)

    svc = CacheService(redis_url="redis://test:6379/0")
    with patch("redis.asyncio.from_url", return_value=fake) as mock_from_url:
        await svc.initialize()
        await svc.initialize()
        await svc.initialize()
    assert mock_from_url.call_count == 1
    assert svc.client is fake


@pytest.mark.asyncio
async def test_initialize_reconnects_after_close():
    from core.cache import CacheService

    fake = AsyncMock()
    fake.ping = AsyncMock(return_value=True)

    svc = CacheService(redis_url="redis://test:6379/0")
    with patch("redis.asyncio.from_url", return_value=fake) as mock_from_url:
        await svc.initialize()
        await svc.close()
        await svc.initialize()
    assert mock_from_url.call_count == 2


# ── RedisClient facade over the shared connection ────────────────────


@pytest.mark.asyncio
async def test_redis_client_delegates_to_shared_connection():
    """Default URL → RedisClient must use the shared cache's raw client."""
    from integrations.cache.redis_client import RedisClient

    fake = FakeRedis()
    stub = StubCache(fake)
    with patch("core.cache.get_cache", return_value=stub):
        client = RedisClient()
        assert client.client is fake  # shared client, no private connection
        assert await client.get("k") is None
        await client.set("k", {"a": 1}, ttl=60)
        assert await client.get("k") == {"a": 1}
        assert await client.exists("k") is True
        assert await client.ping() is True
        await client.delete("k")
        assert await client.exists("k") is False


@pytest.mark.asyncio
async def test_redis_client_never_opens_second_connection_for_default_url():
    """connect() with the default URL must only init the shared cache."""
    from integrations.cache.redis_client import RedisClient

    stub = StubCache(FakeRedis())
    with patch("core.cache.get_cache", return_value=stub), patch(
        "redis.asyncio.from_url"
    ) as mock_from_url:
        client = RedisClient()
        await client.connect()
        mock_from_url.assert_not_called()
        assert stub.initialize_calls == 1


@pytest.mark.asyncio
async def test_redis_client_custom_url_uses_private_connection():
    """Custom URL → RedisClient manages its own connection (legacy path)."""
    from integrations.cache.redis_client import RedisClient

    own = AsyncMock()
    own.ping = AsyncMock(return_value=True)

    stub = StubCache(None)
    with patch("core.cache.get_cache", return_value=stub), patch(
        "redis.asyncio.from_url", return_value=own
    ) as mock_from_url:
        client = RedisClient(url="redis://custom:6379/5")
        await client.connect()
        mock_from_url.assert_called_once_with("redis://custom:6379/5", decode_responses=True)
        assert client.client is own
        await client.disconnect()
        own.close.assert_awaited_once()
        assert client.client is None


@pytest.mark.asyncio
async def test_redis_client_noop_when_redis_unavailable():
    from integrations.cache.redis_client import RedisClient

    stub = StubCache(None, ping_ok=False)
    with patch("core.cache.get_cache", return_value=stub):
        client = RedisClient()
        assert await client.get("k") is None
        await client.set("k", 1)  # no-op
        assert await client.delete("k") is False
        assert await client.exists("k") is False
        assert await client.ttl("k") == -2
        assert await client.keys() == []
        assert await client.incr("k") == 0
        assert await client.smembers("s") == set()
        assert await client.ping() is False
        await client.clear()  # no-op


@pytest.mark.asyncio
async def test_redis_client_raw_commands_via_shared():
    """Set/publish helpers keep working through the shared raw client."""
    from integrations.cache.redis_client import RedisClient

    fake = FakeRedis()
    stub = StubCache(fake)
    with patch("core.cache.get_cache", return_value=stub):
        client = RedisClient()
        assert await client.sadd("set:1", "a", "b") == 2
        assert await client.smembers("set:1") == {"a", "b"}
        assert await client.srem("set:1", "a") == 1
        assert await client.incr("ctr") == 1
        assert await client.ttl("ctr") == 300
        assert await client.publish("chan", {"x": 1}) == 1


# ── Housekeeping jobs use the shared cache ────────────────────────────


@pytest.mark.asyncio
async def test_cache_warmup_job_warms_shared_cache():
    from jobs.definitions.housekeeping_jobs import CacheWarmupJob
    from jobs.job_context import JobContext

    fake = FakeRedis()
    stub = StubCache(fake)
    job = CacheWarmupJob()
    ctx = JobContext(job_id="j1", job_name=job.name, params={"instrument_ids": ["a", "b", "a"]})
    with patch("core.cache.get_cache", return_value=stub):
        result = await job.run(ctx)
    assert result.success is True
    assert result.data["warmed"] == 2  # duplicates not double-counted
    assert json.loads(await fake.get("instrument:a")) == {"id": "a", "warmed": True}


@pytest.mark.asyncio
async def test_health_check_job_reports_redis_ok():
    from jobs.definitions.housekeeping_jobs import HealthCheckJob
    from jobs.job_context import JobContext

    stub = StubCache(FakeRedis(), ping_ok=True)
    job = HealthCheckJob()
    ctx = JobContext(job_id="j1", job_name=job.name)
    with patch("core.cache.get_cache", return_value=stub):
        result = await job.run(ctx)
    assert result.success is True
    assert result.data["checks"]["redis"] == "ok"
    assert result.data["checks"]["config"] == "ok"


@pytest.mark.asyncio
async def test_health_check_job_reports_unreachable_when_ping_fails():
    from jobs.definitions.housekeeping_jobs import HealthCheckJob
    from jobs.job_context import JobContext

    stub = StubCache(None, ping_ok=False)
    job = HealthCheckJob()
    ctx = JobContext(job_id="j1", job_name=job.name)
    with patch("core.cache.get_cache", return_value=stub):
        result = await job.run(ctx)
    assert result.success is True
    assert result.data["checks"]["redis"] == "unreachable"
