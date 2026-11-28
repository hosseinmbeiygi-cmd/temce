"""Regression tests for audit finding F11 — retry counters survive restarts via Redis
(ممیزی 2026-11-28).

Previously ``JobRetryPolicy`` kept counters in a plain instance dict: a worker restart
reset them (a crash-looping job retried forever) and two workers counted
independently. Counters now live in Redis with a 24h TTL, with the old dict as the
no-Redis fallback.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.retry_policy import JobRetryPolicy


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def incr(self, key: str) -> int:
        value = int(self.store.get(key) or 0) + 1
        self.store[key] = value
        return value

    async def expire(self, key: str, ttl: int) -> None:
        self.store[f"{key}:ttl"] = ttl

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.store.pop(key, None)


@pytest.mark.asyncio
async def test_counter_survives_a_worker_restart():
    redis = FakeRedis()
    first = JobRetryPolicy(max_retries=3, redis_client=redis)
    assert await first.record_retry("job_x") == 1
    # A new policy instance (the "restarted" worker) sharing Redis sees the count.
    second = JobRetryPolicy(max_retries=3, redis_client=redis)
    assert await second._count("job_x") == 1
    assert await second.should_retry("job_x") is True


@pytest.mark.asyncio
async def test_respects_max_retries_across_instances():
    redis = FakeRedis()
    policy_a = JobRetryPolicy(max_retries=2, redis_client=redis)
    policy_b = JobRetryPolicy(max_retries=2, redis_client=redis)
    await policy_a.record_retry("job_y")
    await policy_b.record_retry("job_y")
    assert await policy_a.should_retry("job_y") is False


@pytest.mark.asyncio
async def test_clear_retries_removes_the_redis_key():
    redis = FakeRedis()
    policy = JobRetryPolicy(max_retries=3, redis_client=redis)
    await policy.record_retry("job_z")
    assert await policy._count("job_z") == 1
    await policy.clear_retries("job_z")
    assert await policy._count("job_z") == 0
    assert await policy.should_retry("job_z") is True


@pytest.mark.asyncio
async def test_in_memory_fallback_without_redis():
    with patch("core.cache.get_cache", side_effect=RuntimeError("no redis")):
        policy = JobRetryPolicy(max_retries=3)  # no explicit client → cache lookup fails
        assert await policy.record_retry("job_w") == 1
        assert await policy.record_retry("job_w") == 2
        assert await policy.should_retry("job_w") is True


@pytest.mark.asyncio
async def test_redis_error_falls_back_to_memory():
    flaky = MagicMock()
    flaky.incr = AsyncMock(side_effect=RuntimeError("redis down"))
    policy = JobRetryPolicy(max_retries=3, redis_client=flaky)
    assert await policy.record_retry("job_v") == 1  # recorded in memory instead


@pytest.mark.asyncio
async def test_wait_sleeps_once_with_backoff():
    policy = JobRetryPolicy(max_retries=3, base_delay=10.0, backoff_factor=2.0,
                            redis_client=FakeRedis())
    await policy.record_retry("job_u")  # count = 1 → delay ≈ 20s (± jitter)
    with patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
        await policy.wait("job_u")
    assert sleep.await_count == 1
    delay = sleep.await_args.args[0]
    assert 10.0 <= delay <= 20.0  # base × factor², halved at worst by jitter
