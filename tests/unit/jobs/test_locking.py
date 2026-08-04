"""Unit tests for jobs.locking — JobLocking (Redis-based distributed lock).

Covers:
  - In-memory fallback path (Redis unavailable) with identical semantics
    to the previous single-process implementation.
  - Redis-backed path via a fake redis client: SET NX PX + Lua release/extend,
    including cross-instance (multi-worker) exclusivity.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

# ── Fake redis client (minimal surface used by JobLocking) ───────────


class FakeRedis:
    """Minimal redis.asyncio fake: set(nx, px), get, exists, eval (1-key Lua)."""

    def __init__(self) -> None:
        # key -> (value, expires_at_monotonic | None)
        self._data: dict[str, tuple[str, float | None]] = {}

    async def set(self, key: str, value: str, nx: bool = False, px: int | None = None) -> bool | None:
        now = time.monotonic()
        entry = self._data.get(key)
        if entry is not None:
            stored_val, exp = entry
            if exp is not None and now >= exp:
                del self._data[key]
            elif nx:
                return None  # key exists and not expired → NX fails
        self._data[key] = (value, (now + px / 1000.0) if px else None)
        return True

    async def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, exp = entry
        if exp is not None and time.monotonic() >= exp:
            del self._data[key]
            return None
        return value

    async def exists(self, key: str) -> int:
        return 1 if await self.get(key) is not None else 0

    async def eval(self, script: str, numkeys: int, *args) -> int:
        key, owner = args[0], args[1]
        if await self.get(key) != owner:
            return 0
        if "del" in script:
            del self._data[key]
            return 1
        if "pexpire" in script:
            ttl_ms = int(args[2])
            self._data[key] = (owner, time.monotonic() + ttl_ms / 1000.0)
            return 1
        return 0


class _RaisingRedis(FakeRedis):
    """Fake redis whose commands raise — simulates a transient Redis error."""

    async def set(self, key: str, value: str, nx: bool = False, px: int | None = None) -> bool | None:
        raise ConnectionError("simulated redis outage")


class _StubCache:
    """Minimal CacheService stand-in exposing the .client property."""

    def __init__(self, client) -> None:
        self._client = client

    @property
    def client(self):
        return self._client


def _make_locking(client=None):
    from jobs.locking import JobLocking

    locking = JobLocking(default_ttl=300.0)
    with patch("jobs.locking.get_cache", return_value=_StubCache(client)):
        yield locking


@pytest.fixture
def mem_locking():
    """JobLocking with Redis unavailable → in-memory fallback."""
    yield from _make_locking(client=None)


@pytest.fixture
def redis_locking():
    """JobLocking backed by a fake redis client."""
    yield from _make_locking(client=FakeRedis())


# ── In-memory fallback path ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_mem_acquire_release_roundtrip(mem_locking):
    assert await mem_locking.acquire("job:a", "worker-1") is True
    assert await mem_locking.is_locked("job:a") is True
    assert await mem_locking.release("job:a", "worker-1") is True
    assert await mem_locking.is_locked("job:a") is False


@pytest.mark.asyncio
async def test_mem_acquire_blocked_by_other_owner(mem_locking):
    assert await mem_locking.acquire("job:a", "worker-1") is True
    assert await mem_locking.acquire("job:a", "worker-2") is False


@pytest.mark.asyncio
async def test_mem_same_owner_reacquire_renews(mem_locking):
    assert await mem_locking.acquire("job:a", "worker-1", ttl=1.0) is True
    assert await mem_locking.acquire("job:a", "worker-1", ttl=1.0) is True


@pytest.mark.asyncio
async def test_mem_lock_expires(mem_locking):
    assert await mem_locking.acquire("job:a", "worker-1", ttl=0.01) is True
    time.sleep(0.03)
    assert await mem_locking.is_locked("job:a") is False
    # After expiry another worker can acquire
    assert await mem_locking.acquire("job:a", "worker-2") is True


@pytest.mark.asyncio
async def test_mem_release_wrong_owner_returns_false(mem_locking):
    assert await mem_locking.acquire("job:a", "worker-1") is True
    assert await mem_locking.release("job:a", "worker-2") is False
    assert await mem_locking.is_locked("job:a") is True
    assert await mem_locking.release("job:a", "worker-1") is True


@pytest.mark.asyncio
async def test_mem_release_missing_key_is_noop_true(mem_locking):
    assert await mem_locking.release("job:ghost", "worker-1") is True


@pytest.mark.asyncio
async def test_mem_extend_only_by_owner(mem_locking):
    assert await mem_locking.acquire("job:a", "worker-1", ttl=0.05) is True
    assert await mem_locking.extend("job:a", "worker-2") is False
    assert await mem_locking.extend("job:a", "worker-1", ttl=300.0) is True
    time.sleep(0.1)
    assert await mem_locking.is_locked("job:a") is True  # still alive


@pytest.mark.asyncio
async def test_mem_get_owner_and_expiry(mem_locking):
    assert await mem_locking.get_owner("job:a") is None
    await mem_locking.acquire("job:a", "worker-1", ttl=0.01)
    assert await mem_locking.get_owner("job:a") == "worker-1"
    time.sleep(0.03)
    assert await mem_locking.get_owner("job:a") is None


@pytest.mark.asyncio
async def test_mem_purge_expired(mem_locking):
    await mem_locking.acquire("job:expired", "w1", ttl=0.01)
    await mem_locking.acquire("job:live", "w1", ttl=300.0)
    time.sleep(0.03)
    assert await mem_locking.purge_expired() == 1
    assert await mem_locking.is_locked("job:live") is True


@pytest.mark.asyncio
async def test_mem_clear(mem_locking):
    await mem_locking.acquire("job:a", "w1")
    await mem_locking.clear()
    assert await mem_locking.is_locked("job:a") is False


# ── Redis-backed path ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redis_acquire_sets_owner(redis_locking):
    assert await redis_locking.acquire("job:a", "worker-1") is True
    assert await redis_locking.get_owner("job:a") == "worker-1"
    assert await redis_locking.is_locked("job:a") is True


@pytest.mark.asyncio
async def test_redis_cross_worker_exclusivity():
    """Two separate JobLocking instances (different workers) share the lock."""
    from jobs.locking import JobLocking

    shared = FakeRedis()
    lock_a = JobLocking()
    lock_b = JobLocking()
    with patch("jobs.locking.get_cache", return_value=_StubCache(shared)):
        assert await lock_a.acquire("job:shared", "worker-1") is True
        assert await lock_b.acquire("job:shared", "worker-2") is False
        assert await lock_b.is_locked("job:shared") is True
        # worker-2 cannot release worker-1's lock
        assert await lock_b.release("job:shared", "worker-2") is False
        assert await lock_b.is_locked("job:shared") is True
        # worker-1 releases; worker-2 can now acquire
        assert await lock_a.release("job:shared", "worker-1") is True
        assert await lock_b.acquire("job:shared", "worker-2") is True


@pytest.mark.asyncio
async def test_redis_ttl_auto_expiry():
    from jobs.locking import JobLocking

    shared = FakeRedis()
    lock = JobLocking()
    with patch("jobs.locking.get_cache", return_value=_StubCache(shared)):
        assert await lock.acquire("job:ttl", "w1", ttl=0.01) is True
        time.sleep(0.03)
        assert await lock.is_locked("job:ttl") is False
        assert await lock.acquire("job:ttl", "w2") is True


@pytest.mark.asyncio
async def test_redis_release_missing_key_is_noop_true(redis_locking):
    assert await redis_locking.release("job:ghost", "w1") is True


@pytest.mark.asyncio
async def test_redis_extend_renews_ttl(redis_locking):
    assert await redis_locking.acquire("job:a", "w1", ttl=0.01) is True
    assert await redis_locking.extend("job:a", "w2") is False
    assert await redis_locking.extend("job:a", "w1", ttl=300.0) is True
    time.sleep(0.03)
    assert await redis_locking.is_locked("job:a") is True


@pytest.mark.asyncio
async def test_redis_purge_expired_noop(redis_locking):
    # Redis keys expire server-side; purge only affects the fallback dict.
    assert await redis_locking.purge_expired() == 0


@pytest.mark.asyncio
async def test_redis_same_owner_reacquire_fails_nx():
    """Redis path: SET NX rejects even the same owner — renew via extend()."""
    from jobs.locking import JobLocking

    locking = JobLocking()
    with patch("jobs.locking.get_cache", return_value=_StubCache(FakeRedis())):
        assert await locking.acquire("job:a", "w1") is True
        assert await locking.acquire("job:a", "w1") is False


@pytest.mark.asyncio
async def test_redis_transient_error_fails_closed():
    """A transient Redis error must NOT fall back to memory (no double-run)."""
    from jobs.locking import JobLocking

    locking = JobLocking()
    with patch("jobs.locking.get_cache", return_value=_StubCache(_RaisingRedis())):
        assert await locking.acquire("job:a", "w1") is False
        assert await locking.is_locked("job:a") is False


@pytest.mark.asyncio
async def test_redis_clear_does_not_delete_shared_lock():
    from jobs.locking import JobLocking

    shared = FakeRedis()
    lock_a = JobLocking()
    lock_b = JobLocking()
    with patch("jobs.locking.get_cache", return_value=_StubCache(shared)):
        await lock_a.acquire("job:shared", "w1")
        await lock_b.clear()  # must NOT release worker-1's redis lock
        assert await lock_b.is_locked("job:shared") is True
