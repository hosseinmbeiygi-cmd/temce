"""Unit tests — ثبت و اجرای job های GoldDesk در رجیستری BrsApi.

قبل از این تغییر ``GOLD_DESK_JOBS`` هیچ‌جا ثبت نمی‌شد و جداول ``gold_*`` هرگز
پر نمی‌شدند. این تست‌ها:
  * حضور هر ۶ job در رجیستری عمومی را تضمین می‌کنند
  * ``list_all_jobs`` را با endpoint_config=None (بلاک‌کنندهٔ قبلی) بررسی می‌کنند
  * مسیر اجرای مستقیم تابع (بدون HTTP) را می‌سنجند
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from brsapi.jobs import gold_desk_jobs as gd
from brsapi.jobs.registry import BrsApiJobRegistry, get_brsapi_job_registry

EXPECTED_JOBS = {
    "gold_snapshot",
    "gold_score_persist",
    "gold_alert_evaluate",
    "gold_fund_nav",
    "gold_portfolio_value",
    "gold_daily_history",
}


def test_gold_desk_jobs_registered_in_shared_registry() -> None:
    registry = get_brsapi_job_registry()
    names = {j.name for j in registry.all}
    assert names >= EXPECTED_JOBS


def test_every_gold_job_has_a_callable() -> None:
    assert set(gd.GOLD_DESK_JOB_FUNCTIONS) == EXPECTED_JOBS
    for job in gd.GOLD_DESK_JOBS:
        assert job.name in gd.GOLD_DESK_JOB_FUNCTIONS
        assert job.endpoint_config is None  # direct function jobs
        assert callable(gd.GOLD_DESK_JOB_FUNCTIONS[job.name])


def test_list_all_jobs_tolerates_direct_jobs() -> None:
    """endpoint_config=None نباید list_all_jobs را کرش کند."""
    registry = get_brsapi_job_registry()
    listed = {row["name"]: row for row in registry.list_all_jobs()}
    assert set(listed) >= EXPECTED_JOBS
    for name in EXPECTED_JOBS:
        assert listed[name]["endpoint"] is None
        assert listed[name]["category"] == "gold_desk"


@pytest.mark.asyncio
async def test_run_job_now_dispatches_direct_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = AsyncMock()
    monkeypatch.setitem(gd.GOLD_DESK_JOB_FUNCTIONS, "gold_snapshot", called)

    registry = get_brsapi_job_registry()
    result = await registry.run_job_now("gold_snapshot")

    called.assert_awaited_once_with(force=True)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_run_job_now_surfaces_direct_job_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(force: bool = False) -> None:
        raise RuntimeError("snapshot exploded")

    monkeypatch.setitem(gd.GOLD_DESK_JOB_FUNCTIONS, "gold_snapshot", boom)

    result = await get_brsapi_job_registry().run_job_now("gold_snapshot")

    assert result["success"] is False
    assert "snapshot exploded" in result["message"]


@pytest.mark.asyncio
async def test_unknown_direct_job_returns_none() -> None:
    registry = BrsApiJobRegistry()
    assert await registry._run_direct_job("not_a_job") is None


@pytest.mark.asyncio
async def test_queue_worker_dispatches_gold_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """در حالت queue، worker باید job تابعی (gold_*) را هم اجرا کند."""
    from jobs.job_dispatcher import JobDispatcher
    from jobs.job_registry import JobRegistry

    called = AsyncMock()
    monkeypatch.setitem(gd.GOLD_DESK_JOB_FUNCTIONS, "gold_score_persist", called)

    dispatcher = JobDispatcher(registry=JobRegistry())
    result = await dispatcher.dispatch("gold_score_persist")

    called.assert_awaited_once()
    assert result.success is True


@pytest.mark.asyncio
async def test_queue_worker_still_rejects_unknown_job() -> None:
    from jobs.job_dispatcher import JobDispatcher
    from jobs.job_registry import JobRegistry

    result = await JobDispatcher(registry=JobRegistry()).dispatch("totally_unknown_job")

    assert result.success is False
    assert "not found" in result.error
