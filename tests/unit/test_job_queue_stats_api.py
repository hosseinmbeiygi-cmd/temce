"""Tests for the ``/jobs/queue/stats`` admin endpoint in apps/api/endpoints/jobs.py.

Covers:
  1. Returns consumer stats + live queue sizes from Redis (LLEN)
  2. Redis unavailable → queue sizes default to 0
  3. Consumer unavailable → success=False error response (no crash)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Minimal redis.asyncio fake supporting llen."""

    def __init__(self, queue_len: int = 3, dead_len: int = 1) -> None:
        self._len = {"job:queue": queue_len, "job:dead": dead_len}
        self.llen_calls: list[str] = []

    async def llen(self, key: str) -> int:
        self.llen_calls.append(key)
        return self._len.get(key, 0)


class _FakeConsumer:
    """Stand-in for JobQueueConsumer with a fixed stats() and redis handle."""

    def __init__(self, redis: _FakeRedis | None) -> None:
        self._redis_client = redis
        self._max_retries = 3
        self._poll_timeout = 1
        self._token = "secret"
        self._queue_name = "job:queue"
        self._dead_queue = "job:dead"

    def _redis(self):
        return self._redis_client

    def stats(self) -> dict:
        return {
            "running": True,
            "queue": self._queue_name,
            "processed": 42,
            "failed": 2,
            "dead_lettered": 1,
            "rejected_auth": 1,
            "uptime_s": 123.4,
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_stats_returns_consumer_and_live_sizes():
    """stats() output + live LLEN sizes for main and dead-letter queues."""
    from apps.api.endpoints import jobs as jobs_mod

    redis = _FakeRedis(queue_len=5, dead_len=2)
    consumer = _FakeConsumer(redis=redis)

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch("jobs.queue_consumer.get_job_queue_consumer", return_value=consumer),
    ):
        mock_settings.job_queue_name = "job:queue"
        mock_settings.job_queue_dead_letter = "job:dead"
        mock_settings.job_queue_enabled = True

        response = await jobs_mod.job_queue_stats()

    assert response.success is True
    data = response.data

    # Consumer diagnostics merged in
    assert data["processed"] == 42
    assert data["failed"] == 2
    assert data["dead_lettered"] == 1
    assert data["rejected_auth"] == 1
    assert data["running"] is True
    assert data["queue"] == "job:queue"

    # Live sizes
    assert data["queue_size"] == 5
    assert data["dead_letter_size"] == 2
    assert data["queue_enabled"] is True

    # Config block
    assert data["config"]["queue"] == "job:queue"
    assert data["config"]["dead_letter"] == "job:dead"
    assert data["config"]["max_retries"] == 3
    assert data["config"]["auth_enabled"] is True

    # Both LLEN calls hit Redis
    assert set(redis.llen_calls) == {"job:queue", "job:dead"}


@pytest.mark.asyncio
async def test_queue_stats_redis_unavailable_sizes_zero():
    """Redis unavailable → queue sizes default to 0, stats still returned."""
    from apps.api.endpoints import jobs as jobs_mod

    consumer = _FakeConsumer(redis=None)

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch("jobs.queue_consumer.get_job_queue_consumer", return_value=consumer),
    ):
        mock_settings.job_queue_name = "job:queue"
        mock_settings.job_queue_dead_letter = "job:dead"
        mock_settings.job_queue_enabled = False

        response = await jobs_mod.job_queue_stats()

    assert response.success is True
    data = response.data
    assert data["queue_size"] == 0
    assert data["dead_letter_size"] == 0
    assert data["queue_enabled"] is False
    assert data["processed"] == 42


@pytest.mark.asyncio
async def test_queue_stats_consumer_missing_returns_error():
    """Failure to read stats → success=False, no crash."""
    from apps.api.endpoints import jobs as jobs_mod

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch("jobs.queue_consumer.get_job_queue_consumer",
              side_effect=RuntimeError("redis down")),
    ):
        mock_settings.job_queue_name = "job:queue"
        mock_settings.job_queue_dead_letter = "job:dead"

        response = await jobs_mod.job_queue_stats()

    assert response.success is False
    assert "message" in (response.error or {})


@pytest.mark.asyncio
async def test_queue_stats_llen_error_tolerated():
    """LLEN raising (e.g. connection reset) → sizes 0, stats still returned."""
    from apps.api.endpoints import jobs as jobs_mod

    class _FlakyRedis:
        async def llen(self, key: str) -> int:
            raise ConnectionError("reset")

    consumer = _FakeConsumer(redis=_FlakyRedis())

    with (
        patch.object(jobs_mod, "settings") as mock_settings,
        patch("jobs.queue_consumer.get_job_queue_consumer", return_value=consumer),
    ):
        mock_settings.job_queue_name = "job:queue"
        mock_settings.job_queue_dead_letter = "job:dead"
        mock_settings.job_queue_enabled = True

        response = await jobs_mod.job_queue_stats()

    assert response.success is True
    assert response.data["queue_size"] == 0
    assert response.data["dead_letter_size"] == 0
