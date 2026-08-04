"""Unit tests for jobs.scheduler — JobScheduler class.

Tests the scheduling lifecycle, job registration, and stats.
"""

from __future__ import annotations

import pytest

# ── Helpers ─────────────────────────────────────────────────


@pytest.fixture
def scheduler():
    from jobs.scheduler import JobScheduler

    return JobScheduler()


# ─── Schedule / Unschedule ──────────────────────────────────


def test_schedule_job(scheduler):
    job = scheduler.schedule_job("test_job", "*/5 * * * *")
    assert job.job_id.startswith("sched-")
    assert job.job_name == "test_job"
    assert job.cron_expression == "*/5 * * * *"
    assert job.enabled is True


def test_schedule_job_with_kwargs(scheduler):
    job = scheduler.schedule_job("data_sync", "0 */2 * * *", source="tsetmc", timeout=30)
    assert job.kwargs == {"source": "tsetmc", "timeout": 30}


def test_unschedule_job_removes_it(scheduler):
    job = scheduler.schedule_job("j1", "*/5 * * * *")
    assert scheduler.unschedule_job(job.job_id) is True
    assert scheduler.get_scheduled_job(job.job_id) is None


def test_unschedule_nonexistent_returns_false(scheduler):
    assert scheduler.unschedule_job("non-existent") is False


# ── Listing / Retrieval ─────────────────────────────────────


def test_list_scheduled_jobs_empty(scheduler):
    assert scheduler.list_scheduled_jobs() == []


def test_list_scheduled_jobs_returns_all(scheduler):
    scheduler.schedule_job("j1", "* * * * *")
    scheduler.schedule_job("j2", "*/5 * * * *")
    jobs = scheduler.list_scheduled_jobs()
    assert len(jobs) == 2
    assert {j.job_name for j in jobs} == {"j1", "j2"}


def test_get_scheduled_job_by_id(scheduler):
    job = scheduler.schedule_job("j1", "* * * * *")
    assert scheduler.get_scheduled_job(job.job_id) is job


# ── Enable / Disable ────────────────────────────────────────


def test_enable_job(scheduler):
    job = scheduler.schedule_job("j1", "* * * * *")
    scheduler.disable_job(job.job_id)
    assert job.enabled is False
    assert scheduler.enable_job(job.job_id) is True
    assert job.enabled is True


def test_disable_job(scheduler):
    job = scheduler.schedule_job("j1", "* * * * *")
    assert scheduler.disable_job(job.job_id) is True
    assert job.enabled is False


def test_enable_nonexistent_returns_false(scheduler):
    assert scheduler.enable_job("no-such-job") is False


def test_disable_nonexistent_returns_false(scheduler):
    assert scheduler.disable_job("no-such-job") is False


# ── Job Function Registration & Execution ───────────────────


@pytest.mark.asyncio
async def test_register_and_run_job(scheduler):
    results = []

    async def my_job(msg: str):
        results.append(msg)
        return {"processed": msg}

    scheduler.register_job_func("my_job", my_job)
    scheduler.schedule_job("my_job", "* * * * *", msg="hello")

    result = await scheduler.run_job_now("sched-000001")
    assert result == {"processed": "hello"}
    assert results == ["hello"]


@pytest.mark.asyncio
async def test_run_job_not_found_returns_none(scheduler):
    result = await scheduler.run_job_now("no-such-job")
    assert result is None


@pytest.mark.asyncio
async def test_run_job_no_func_registered_returns_none(scheduler):
    scheduler.schedule_job("orphan", "* * * * *")
    result = await scheduler.run_job_now("sched-000001")
    assert result is None


@pytest.mark.asyncio
async def test_run_job_exception_returns_none(scheduler):
    async def failing_job():
        raise ValueError("oops")

    scheduler.register_job_func("failing", failing_job)
    scheduler.schedule_job("failing", "* * * * *")
    result = await scheduler.run_job_now("sched-000001")
    assert result is None


@pytest.mark.asyncio
async def test_run_job_updates_last_run(scheduler):
    async def my_job():
        return "done"

    scheduler.register_job_func("my_job", my_job)
    scheduler.schedule_job("my_job", "* * * * *")
    job = scheduler.get_scheduled_job("sched-000001")
    assert job is not None
    assert job.last_run is None

    await scheduler.run_job_now("sched-000001")
    assert job.last_run is not None


# ── Start / Stop ────────────────────────────────────────────


def test_start_scheduler(scheduler):
    scheduler.start()
    assert scheduler.is_running is True


def test_stop_scheduler(scheduler):
    scheduler.start()
    scheduler.stop()
    assert scheduler.is_running is False


def test_is_running_defaults_to_false(scheduler):
    assert scheduler.is_running is False


# ── Stats ───────────────────────────────────────────────────


def test_get_stats(scheduler):
    scheduler.schedule_job("j1", "* * * * *")
    scheduler.schedule_job("j2", "*/5 * * * *")
    scheduler.disable_job("sched-000002")

    async def my_func():
        pass

    scheduler.register_job_func("j1", my_func)
    scheduler.start()

    stats = scheduler.get_stats()
    assert stats["total_scheduled"] == 2
    assert stats["enabled"] == 1
    assert stats["disabled"] == 1
    assert stats["running"] is True
    assert "j1" in stats["registered_funcs"]


def test_get_stats_empty(scheduler):
    stats = scheduler.get_stats()
    assert stats["total_scheduled"] == 0
    assert stats["enabled"] == 0
    assert stats["disabled"] == 0
    assert stats["running"] is False
    assert stats["registered_funcs"] == []
