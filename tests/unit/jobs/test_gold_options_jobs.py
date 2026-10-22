"""STEP 5-FIX-2: daily per-contract IV snapshot job.

Covers:
  - ``GoldOptionIvSnapshotJob`` wires the snapshot service and reports counts
  - an unexpected error degrades to a failed result (never crashes scheduler)
  - the job is registered in ``job_registry`` and scheduled by ``SchedulerApp``
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs import definitions as job_definitions
from jobs.definitions.gold_options_jobs import GoldOptionIvSnapshotJob
from jobs.job_context import JobContext


def _make_context() -> JobContext:
    return JobContext(
        job_id="options-job-1", job_name="GoldOptionIvSnapshotJob", params={}
    )


def _make_get_session(session: MagicMock):
    async def _gen():
        yield session

    return _gen


class TestGoldOptionIvSnapshotJob:
    @pytest.mark.asyncio
    async def test_execute_stores_snapshot_and_reports_counts(self) -> None:
        session = MagicMock()
        snapshot = AsyncMock(
            return_value={
                "scanned": 2,
                "stored": 2,
                "inserted": 2,
                "updated": 0,
                "skipped": 0,
                "missing_iv": 0,
            }
        )

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch(
                "services.gold.options_chain_service.snapshot_option_iv", snapshot
            ),
        ):
            result = await GoldOptionIvSnapshotJob().execute(_make_context())

        assert result.success is True, getattr(result, "error", None)
        assert result.data["inserted"] == 2
        assert result.data["stored"] == 2
        snapshot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_failure_returns_failed_result(self) -> None:
        session = MagicMock()
        snapshot = AsyncMock(side_effect=RuntimeError("db down"))

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch(
                "services.gold.options_chain_service.snapshot_option_iv", snapshot
            ),
        ):
            result = await GoldOptionIvSnapshotJob().execute(_make_context())

        assert result.success is False
        assert "db down" in (result.error or "")

    @pytest.mark.asyncio
    async def test_missing_db_session_returns_failed_result(self) -> None:
        async def _empty_gen():
            return
            yield  # pragma: no cover - makes this an async generator

        with patch("core.database.get_session", _empty_gen):
            result = await GoldOptionIvSnapshotJob().execute(_make_context())

        assert result.success is False

    def test_job_is_exported_from_definitions(self) -> None:
        assert hasattr(job_definitions, "GoldOptionIvSnapshotJob")

    def test_job_is_registered(self) -> None:
        from jobs.registry import job_registry

        job_registry.register_module(job_definitions)
        assert "GoldOptionIvSnapshotJob" in job_registry.list_names()

    def test_job_is_scheduled_daily(self) -> None:
        from apps.scheduler.app import SchedulerApp

        source = inspect.getsource(SchedulerApp.start)
        assert '"GoldOptionIvSnapshotJob"' in source
