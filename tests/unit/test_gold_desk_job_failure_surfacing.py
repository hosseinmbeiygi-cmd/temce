"""GoldDesk direct-function jobs must surface failures, not fake success.

Each ``job_gold_*`` body used to log-and-swallow every exception, so
``BrsApiJobRegistry._run_direct_job`` (which treats "no exception" as success)
always reported ``success=True`` even when the DB was down or the snapshot
raised. That turned real incidents into green ``[OK]`` job reports and hid the
work from the queue's retry / dead-letter path.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from brsapi.jobs import gold_desk_jobs as gd
from brsapi.jobs.registry import BrsApiJobRegistry


async def _raise(*_args, **_kwargs):
    raise RuntimeError("snapshot exploded")


async def _fake_session():
    """Async generator standing in for ``core.database.get_session`` so the
    test never touches PostgreSQL."""
    yield object()


@pytest.mark.asyncio
async def test_snapshot_failure_is_reported_as_failure() -> None:
    registry = BrsApiJobRegistry()
    with (
        patch.object(gd, "get_session", _fake_session),
        patch.object(gd.snapshot_service, "build_snapshot", _raise),
    ):
        report = await registry._run_direct_job("gold_snapshot")

    assert report is not None
    assert report.success is False
    assert "snapshot exploded" in (report.error or "")


@pytest.mark.asyncio
async def test_run_job_now_reports_failure_to_caller() -> None:
    registry = BrsApiJobRegistry()
    registry.register_many(gd.GOLD_DESK_JOBS)
    with (
        patch.object(gd, "get_session", _fake_session),
        patch.object(gd.snapshot_service, "build_snapshot", _raise),
    ):
        result = await registry.run_job_now("gold_snapshot")

    assert result["success"] is False


@pytest.mark.asyncio
async def test_successful_job_still_reports_success() -> None:
    """The happy path must stay green (no over-eager failure surfacing)."""
    registry = BrsApiJobRegistry()
    # ``gold_daily_history`` is a genuine no-op that never raises.
    report = await registry._run_direct_job("gold_daily_history")
    assert report is not None
    assert report.success is True
