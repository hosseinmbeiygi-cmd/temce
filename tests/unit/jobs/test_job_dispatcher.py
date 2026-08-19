"""Unit tests for the JobDispatcher.

Covers:
  - unknown job → failure
  - deduplication short-circuit
  - lock-not-acquired short-circuit
  - successful dispatch (job.run called, retry cleared, lock released)
  - job exception → failure
  - job create failure
  - ``list_jobs``

Uses fakes for the registry, locking, deduplicator and retry policy.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jobs.job_dispatcher import JobDispatcher
from jobs.job_result import JobResult


def _make_job_cls(result: JobResult) -> MagicMock:
    """Registry stub returning a job class whose run() returns ``result``."""
    job = MagicMock()
    job.run = AsyncMock(return_value=result)
    job_cls = MagicMock(return_value=job)
    return job_cls


def _make_dispatcher(
    job_cls: MagicMock | None = None,
    registry: MagicMock | None = None,
    locking: AsyncMock | None = None,
    deduplicator: AsyncMock | None = None,
    retry_policy: MagicMock | None = None,
) -> tuple[JobDispatcher, dict[str, MagicMock]]:
    registry = registry or MagicMock()
    if job_cls is not None:
        registry.get.return_value = job_cls
        registry.create.return_value = job_cls.return_value

    locking = locking or AsyncMock()
    locking.acquire = AsyncMock(return_value=True)
    locking.release = AsyncMock(return_value=True)

    deduplicator = deduplicator or AsyncMock()
    deduplicator.is_duplicate = AsyncMock(return_value=False)
    deduplicator.mark = AsyncMock()

    retry_policy = retry_policy or MagicMock()
    retry_policy.clear_retries = MagicMock()

    dispatcher = JobDispatcher(
        registry=registry,
        locking=locking,
        deduplicator=deduplicator,
        retry_policy=retry_policy,
    )
    mocks = {
        "registry": registry,
        "locking": locking,
        "deduplicator": deduplicator,
        "retry_policy": retry_policy,
    }
    return dispatcher, mocks


# ── dispatch ──────────────────────────────────────────────────────────────


class TestDispatch:
    @pytest.mark.asyncio
    async def test_unknown_job_returns_failure(self) -> None:
        dispatcher, mocks = _make_dispatcher()
        mocks["registry"].get.return_value = None

        result = await dispatcher.dispatch("DoesNotExist")

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_success_path(self) -> None:
        job_result = JobResult.success_result(job_name="SyncQuotesJob", data={"x": 1})
        job_cls = _make_job_cls(job_result)
        dispatcher, mocks = _make_dispatcher(job_cls=job_cls)

        result = await dispatcher.dispatch("SyncQuotesJob", params={"limit": 10})

        assert result.success is True
        assert result.data == {"x": 1}
        # The job is created via the registry and its run() is awaited.
        mocks["registry"].create.assert_called_once_with("SyncQuotesJob")
        job_cls.return_value.run.assert_awaited_once()
        mocks["deduplicator"].is_duplicate.assert_awaited_once()
        mocks["deduplicator"].mark.assert_awaited_once()
        mocks["locking"].acquire.assert_awaited_once()
        mocks["locking"].release.assert_awaited_once()
        mocks["retry_policy"].clear_retries.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_job_short_circuits(self) -> None:
        job_cls = _make_job_cls(JobResult.success_result())
        dispatcher, mocks = _make_dispatcher(job_cls=job_cls)
        mocks["deduplicator"].is_duplicate = AsyncMock(return_value=True)

        result = await dispatcher.dispatch("SyncQuotesJob")

        assert result.success is False
        assert "Duplicate" in result.error
        job_cls.assert_not_called()
        mocks["locking"].acquire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lock_not_acquired_short_circuits(self) -> None:
        job_cls = _make_job_cls(JobResult.success_result())
        dispatcher, mocks = _make_dispatcher(job_cls=job_cls)
        mocks["locking"].acquire = AsyncMock(return_value=False)

        result = await dispatcher.dispatch("SyncQuotesJob")

        assert result.success is False
        assert "Lock not acquired" in result.error
        job_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_job_exception_returns_failure_and_releases_lock(self) -> None:
        job = MagicMock()
        job.run = AsyncMock(side_effect=RuntimeError("crash"))
        job_cls = MagicMock(return_value=job)
        dispatcher, mocks = _make_dispatcher(job_cls=job_cls)

        result = await dispatcher.dispatch("SyncQuotesJob")

        assert result.success is False
        assert "crash" in result.error
        mocks["locking"].release.assert_awaited_once()
        # Retries are only cleared on success — never on failure.
        mocks["retry_policy"].clear_retries.assert_not_called()

    @pytest.mark.asyncio
    async def test_job_create_failure(self) -> None:
        registry = MagicMock()
        registry.get.return_value = MagicMock()  # class found…
        registry.create.return_value = None  # …but cannot be instantiated
        dispatcher, mocks = _make_dispatcher(registry=registry)

        result = await dispatcher.dispatch("SyncQuotesJob")

        assert result.success is False
        assert "Could not create job" in result.error


# ── list_jobs ─────────────────────────────────────────────────────────────


class TestListJobs:
    @pytest.mark.asyncio
    async def test_returns_registry_names(self) -> None:
        dispatcher, mocks = _make_dispatcher()
        mocks["registry"].list_names.return_value = ["A", "B"]

        names = dispatcher.list_jobs()

        assert names == ["A", "B"]
