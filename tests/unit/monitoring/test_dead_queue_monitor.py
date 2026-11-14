"""DeadQueueMonitorJob / JobMonitor.check_dead_queue against a fake Redis."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from core.config import settings
from jobs.definitions import DeadQueueMonitorJob
from jobs.job_context import JobContext
from jobs.registry import job_registry
from monitoring.job_monitor import JobMonitor


class _FakeRedis:
    def __init__(self, lengths: dict[str, int]) -> None:
        self._lengths = lengths
        self.asked: list[str] = []

    async def llen(self, key: str) -> int:
        self.asked.append(key)
        return self._lengths.get(key, 0)


def _cache(client: object) -> SimpleNamespace:
    return SimpleNamespace(client=client)


async def test_reads_the_configured_dead_letter_key() -> None:
    redis = _FakeRedis({settings.job_queue_dead_letter: 3})
    monitor = JobMonitor()
    with patch("core.cache.get_cache", return_value=_cache(redis)):
        assert await monitor.check_dead_queue() == 3
    assert redis.asked == [settings.job_queue_dead_letter]
    assert monitor.report()["dead_queue_length"] == 3


async def test_fails_open_without_redis() -> None:
    with patch("core.cache.get_cache", return_value=_cache(None)):
        assert await JobMonitor().check_dead_queue() == 0


async def test_fails_open_when_redis_raises() -> None:
    class _Broken:
        async def llen(self, key: str) -> int:
            raise ConnectionError("down")

    with patch("core.cache.get_cache", return_value=_cache(_Broken())):
        assert await JobMonitor().check_dead_queue() == 0


async def test_job_reports_queue_length() -> None:
    redis = _FakeRedis({settings.job_queue_dead_letter: 7})
    job = DeadQueueMonitorJob()
    ctx = JobContext(job_id="t-1", job_name=job.name, params={})
    with patch("core.cache.get_cache", return_value=_cache(redis)):
        result = await job.run(ctx)
    assert result.success
    assert result.data == {"dead_queue_length": 7}


def test_job_is_resolvable_by_the_scheduler_name() -> None:
    from jobs import definitions

    job_registry.register_module(definitions)
    assert job_registry.get("DeadQueueMonitorJob") is DeadQueueMonitorJob
