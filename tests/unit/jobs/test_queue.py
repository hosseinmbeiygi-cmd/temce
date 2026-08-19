"""Unit tests for the distributed job queue (jobs.queue_publisher / queue_consumer).

Covers:
  - ``RedisJobLock`` facade (acquire/release/extend with owner safety).
  - ``JobQueuePublisher`` (LPUSH + auth token).
  - ``JobQueueConsumer`` (auth check, dispatch, benign lock-skip, retry → dead-letter).

Uses a fake ``redis.asyncio`` client — no real Redis needed.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from jobs.queue_consumer import JobQueueConsumer
from jobs.queue_publisher import JobQueuePublisher


# ── Fake redis client (lists + locks) ────────────────────────────────────


class FakeRedis:
    """Minimal redis.asyncio fake: locks (set nx px / get / exists / eval)
    plus list ops used by the queue (lpush / brpop / llen)."""

    def __init__(self) -> None:
        self._locks: dict[str, tuple[str, float | None]] = {}  # key -> (value, expires_at)
        self._lists: dict[str, list[str]] = {}

    # ── Lock primitives ──
    async def set(self, key: str, value: str, nx: bool = False, px: int | None = None) -> bool | None:
        import time

        now = time.monotonic()
        entry = self._locks.get(key)
        if entry is not None:
            stored_val, exp = entry
            if exp is not None and now >= exp:
                del self._locks[key]
            elif nx:
                return None
        self._locks[key] = (value, (now + px / 1000.0) if px else None)
        return True

    async def get(self, key: str) -> str | None:
        import time

        entry = self._locks.get(key)
        if entry is None:
            return None
        value, exp = entry
        if exp is not None and time.monotonic() >= exp:
            del self._locks[key]
            return None
        return value

    async def exists(self, key: str) -> int:
        return 1 if await self.get(key) is not None else 0

    async def eval(self, script: str, numkeys: int, *args) -> int:
        import time

        key, owner = args[0], args[1]
        if await self.get(key) != owner:
            return 0
        if "del" in script:
            del self._locks[key]
            return 1
        if "pexpire" in script:
            ttl_ms = int(args[2])
            self._locks[key] = (owner, time.monotonic() + ttl_ms / 1000.0)
            return 1
        return 0

    # ── List primitives ──
    async def lpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, [])
        self._lists[key] = list(values) + self._lists[key]
        return len(self._lists[key])

    async def brpop(self, key: str, timeout: int = 0) -> list[str] | None:
        await asyncio.sleep(0)  # yield to the event loop
        lst = self._lists.get(key)
        if lst:
            return [key, lst.pop()]
        return None

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))


# ── Fake dispatcher ──────────────────────────────────────────────────────


class FakeDispatcher:
    def __init__(self, result=None):
        from jobs.job_result import JobResult

        self.result = result or JobResult.success_result(job_name="SyncQuotesJob")
        self.calls: list[dict] = []

    async def dispatch(self, job_name, params=None, context=None):
        self.calls.append({"job_name": job_name, "params": params or {}, "context": context})
        return self.result


def _decode(raw: str) -> dict:
    return json.loads(raw)


# ── RedisJobLock ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redis_job_lock_acquire_release_owner_safe():
    from jobs.locking import RedisJobLock

    client = FakeRedis()
    lock_a = RedisJobLock(ttl=300)
    lock_b = RedisJobLock(ttl=300)
    # Inject the fake client (skip get_cache path).
    lock_a._redis = lambda: client  # type: ignore[method-assign]
    lock_b._redis = lambda: client  # type: ignore[method-assign]

    assert await lock_a.acquire("sync_quotes") is True
    assert await lock_a.is_locked("sync_quotes") is True
    # Second worker cannot acquire while A holds it.
    assert await lock_b.acquire("sync_quotes") is False
    # B cannot release A's lock.
    assert await lock_b.release("sync_quotes") is False
    # A can.
    assert await lock_a.release("sync_quotes") is True
    # Now B can acquire.
    assert await lock_b.acquire("sync_quotes") is True


@pytest.mark.asyncio
async def test_redis_job_lock_extend_only_owner():
    from jobs.locking import RedisJobLock

    client = FakeRedis()
    lock_a = RedisJobLock(ttl=300)
    lock_b = RedisJobLock(ttl=300)
    lock_a._redis = lambda: client  # type: ignore[method-assign]
    lock_b._redis = lambda: client  # type: ignore[method-assign]

    await lock_a.acquire("long_job")
    assert await lock_b.extend("long_job", ttl=600) is False
    assert await lock_a.extend("long_job", ttl=600) is True


# ── JobQueuePublisher ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publisher_pushes_job_with_token():
    client = FakeRedis()
    pub = JobQueuePublisher(redis_client=client, queue_name="job:queue", token="secret-token")

    msg_id = await pub.publish("SyncQuotesJob", params={"limit": 100})

    assert msg_id is not None
    assert await pub.queue_size() == 1
    raw = client._lists["job:queue"][0]
    payload = _decode(raw)
    assert payload["job_name"] == "SyncQuotesJob"
    assert payload["params"] == {"limit": 100}
    assert payload["token"] == "secret-token"
    assert payload["type"] == "job"


@pytest.mark.asyncio
async def test_publisher_returns_none_when_redis_unavailable():
    class _StubCache:
        client = None

    with patch("core.cache.get_cache", return_value=_StubCache()):
        pub = JobQueuePublisher(redis_client=None, queue_name="job:queue")
        # No client anywhere → publish returns None (caller falls back).
        assert await pub.publish("SyncQuotesJob") is None
        assert pub.is_available is False


# ── JobQueueConsumer ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consumer_executes_job():
    from jobs.job_result import JobResult

    client = FakeRedis()
    dispatcher = FakeDispatcher(result=JobResult.success_result(job_name="SyncQuotesJob"))
    consumer = JobQueueConsumer(
        redis_client=client,
        queue_name="job:queue",
        token="secret-token",
        dispatcher=dispatcher,
    )

    pub = JobQueuePublisher(redis_client=client, queue_name="job:queue", token="secret-token")
    await pub.publish("SyncQuotesJob", params={"x": 1})

    await consumer._handle_message(client._lists["job:queue"].pop())

    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0]["job_name"] == "SyncQuotesJob"
    assert dispatcher.calls[0]["params"] == {"x": 1}
    assert consumer.processed == 1


@pytest.mark.asyncio
async def test_consumer_rejects_invalid_token():
    client = FakeRedis()
    dispatcher = FakeDispatcher()
    consumer = JobQueueConsumer(
        redis_client=client,
        queue_name="job:queue",
        token="expected-token",
        dispatcher=dispatcher,
    )
    pub = JobQueuePublisher(redis_client=client, queue_name="job:queue", token="attacker-token")
    await pub.publish("SyncQuotesJob")

    await consumer._handle_message(client._lists["job:queue"].pop())

    assert len(dispatcher.calls) == 0
    assert consumer.rejected_auth == 1


@pytest.mark.asyncio
async def test_consumer_skips_lock_failure_as_benign():
    from jobs.job_result import JobResult

    client = FakeRedis()
    dispatcher = FakeDispatcher(result=JobResult.failure("Lock not acquired for SyncQuotesJob", job_name="SyncQuotesJob"))
    consumer = JobQueueConsumer(
        redis_client=client,
        queue_name="job:queue",
        token="t",
        dispatcher=dispatcher,
    )
    pub = JobQueuePublisher(redis_client=client, queue_name="job:queue", token="t")
    await pub.publish("SyncQuotesJob")

    await consumer._handle_message(client._lists["job:queue"].pop())

    # Lock failure = another worker is running it → counted as processed, no requeue.
    assert len(dispatcher.calls) == 1
    assert consumer.processed == 1
    assert consumer.failed == 0
    assert await client.llen("job:retry") == 0


@pytest.mark.asyncio
async def test_consumer_requeues_then_dead_letters():
    from jobs.job_result import JobResult

    client = FakeRedis()
    dispatcher = FakeDispatcher(result=JobResult.failure("boom", job_name="SyncCodalJob"))
    consumer = JobQueueConsumer(
        redis_client=client,
        queue_name="job:queue",
        token="t",
        dispatcher=dispatcher,
        max_retries=2,
    )

    # Attempt 1 → requeued back onto the MAIN queue with attempt=2.
    await consumer._handle_message(json.dumps({
        "type": "job",
        "job_name": "SyncCodalJob",
        "params": {},
        "job_id": "job-1",
        "token": "t",
        "attempt": 1,
    }))
    assert await client.llen("job:queue") == 1
    assert consumer.failed == 1
    # BRPOP semantics: the message is *removed* from the queue before handling.
    requeued = _decode(client._lists["job:queue"].pop())
    assert requeued["attempt"] == 2

    # Attempt 2 (>= max_retries) → dead-letter.
    await consumer._handle_message(json.dumps(requeued))
    assert await client.llen("job:queue") == 0
    assert await client.llen("job:dead") == 1
    assert consumer.dead_lettered == 1
    assert consumer.failed == 2
    dead = _decode(client._lists["job:dead"][0])
    assert dead["attempt"] == 2
    assert "boom" in dead.get("error", "")
