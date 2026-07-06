"""Unit tests for apps.scheduler.app — SchedulerApp class.

Tests APScheduler integration, job registration, and lifecycle.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def scheduler_app():
    """Create a SchedulerApp instance with a mocked APScheduler."""
    from apps.scheduler.app import SchedulerApp

    app = SchedulerApp()
    # Replace the real APScheduler with a mock so tests don't start threads
    app.scheduler = MagicMock()
    return app


# ── Initialization ──────────────────────────────────────────

def test_init_creates_scheduler():
    """Verify SchedulerApp creates an AsyncIOScheduler on init."""
    from apps.scheduler.app import SchedulerApp
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    app = SchedulerApp()
    assert isinstance(app.scheduler, AsyncIOScheduler)
    if app.scheduler.running:
        app.scheduler.shutdown(wait=False)


# ── add_job ─────────────────────────────────────────────────

def test_add_job_calls_scheduler_add_job(scheduler_app):
    """add_job should delegate to APScheduler's add_job."""
    scheduler_app.add_job("sync_quotes", trigger="interval", minutes=5)
    scheduler_app.scheduler.add_job.assert_called_once()
    # The first arg is the wrapper function, second is the trigger type
    call_args = scheduler_app.scheduler.add_job.call_args
    assert call_args[0][1] == "interval"  # trigger
    assert "minutes" in call_args[1]
    assert call_args[1]["minutes"] == 5


def test_add_job_default_trigger_is_interval(scheduler_app):
    """Default trigger should be 'interval'."""
    scheduler_app.add_job("test_job")
    call_args = scheduler_app.scheduler.add_job.call_args
    assert call_args[0][1] == "interval"


# ── start ────────────────────────────────────────────────────

def test_start_adds_default_jobs(scheduler_app):
    """start() should register legacy jobs (SyncInstrumentsJob, SyncQuotesJob, SyncCodalJob, NewsIngestionJob) + BrsApi registry jobs."""
    scheduler_app.start()
    # APScheduler.start() must be called
    scheduler_app.scheduler.start.assert_called_once()
    # 4 legacy jobs + BrsApi registry jobs = at least 4
    assert scheduler_app.scheduler.add_job.call_count >= 4


def test_start_adds_sync_instruments(scheduler_app):
    scheduler_app.start()
    calls = scheduler_app.scheduler.add_job.call_args_list
    # Check sync_instruments was added with hours=24
    instrument_call = None
    for call in calls:
        kwargs = call[1]
        if "hours" in kwargs and kwargs.get("hours") == 24:
            instrument_call = call
            break
    assert instrument_call is not None, "sync_instruments job not found with hours=24"


def test_start_adds_sync_quotes(scheduler_app):
    scheduler_app.start()
    calls = scheduler_app.scheduler.add_job.call_args_list
    quote_call = None
    for call in calls:
        kwargs = call[1]
        if "minutes" in kwargs and kwargs.get("minutes") == 5:
            quote_call = call
            break
    assert quote_call is not None, "sync_quotes job not found with minutes=5"


def test_start_adds_sync_codal(scheduler_app):
    scheduler_app.start()
    calls = scheduler_app.scheduler.add_job.call_args_list
    codal_call = None
    for call in calls:
        kwargs = call[1]
        if "hours" in kwargs and kwargs.get("hours") == 6:
            codal_call = call
            break
    assert codal_call is not None, "sync_codal job not found with hours=6"


def test_start_adds_sync_news(scheduler_app):
    scheduler_app.start()
    calls = scheduler_app.scheduler.add_job.call_args_list
    news_call = None
    for call in calls:
        kwargs = call[1]
        if "hours" in kwargs and kwargs.get("hours") == 1:
            news_call = call
            break
    assert news_call is not None, "sync_news job not found with hours=1"


# ── run_forever ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_forever_calls_start():
    """Verify run_forever calls start() then sleeps."""
    from apps.scheduler.app import SchedulerApp

    app = SchedulerApp()
    app.scheduler = MagicMock()

    # Mock asyncio.sleep to raise CancelledError on first call so the loop exits
    import asyncio

    async def run_until_start():
        task = asyncio.create_task(app.run_forever())
        # Give the event loop a chance to execute the task
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await run_until_start()

    # start() should have been called
    app.scheduler.start.assert_called_once()


# ── Job Wrapper ─────────────────────────────────────────────

def test_add_job_wrapper_calls_dispatcher(scheduler_app):
    """The wrapper function inside add_job should call job_dispatcher.dispatch."""
    from unittest.mock import patch
    from jobs.job_dispatcher import job_dispatcher

    # Actually grab the wrapper via the mock call
    scheduler_app.add_job("sync_test", trigger="interval", seconds=1)
    call_args = scheduler_app.scheduler.add_job.call_args
    wrapper_fn = call_args[0][0]

    # Call the wrapper and verify it dispatches
    with patch.object(job_dispatcher, "dispatch", new_callable=AsyncMock) as mock_dispatch:
        import asyncio
        asyncio.run(wrapper_fn())
        mock_dispatch.assert_awaited_once_with("sync_test")
