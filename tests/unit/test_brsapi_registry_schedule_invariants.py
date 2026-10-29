"""Offline structural invariants for the BrsApi job registry.

These do not touch the network or the DB. They pin the properties that make
the scheduler safe and quota-aware, so a future edit that drops a
``market_hours_only`` flag, breaks a crontab, collides two job names or two
APScheduler ids fails loudly here instead of quietly burning the free BrsApi
daily quota or silently not firing a job.
"""

from __future__ import annotations

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from brsapi.jobs.registry import get_brsapi_job_registry

# Jobs whose intent is "only poll while the Tehran market is open" â€” the free
# BrsApi tier's daily quota is reserved for these.
_REALTIME_MARKET_JOBS = (
    "brsapi_all_symbols",
    "brsapi_index",
    "brsapi_index_farabours",
    "brsapi_options",
    "brsapi_ime_futures",
    "brsapi_ime_options",
    "brsapi_ime_certificates",
    "brsapi_ime_funds",
)


def test_job_names_are_unique() -> None:
    registry = get_brsapi_job_registry()
    names = [job.name for job in registry.all]
    assert len(names) == len(set(names)), f"duplicate job names: {names}"
    assert all(name for name in names), "a job has an empty name"


def test_every_cron_is_valid_crontab_or_positive_interval() -> None:
    import pytz

    registry = get_brsapi_job_registry()
    tz = pytz.timezone("Asia/Tehran")
    for job in registry.all:
        if isinstance(job.cron, int):
            assert job.cron > 0, f"{job.name}: interval seconds must be positive"
        elif isinstance(job.cron, str):
            # Raises ValueError on a malformed expression.
            CronTrigger.from_crontab(job.cron, timezone=tz)
        else:
            pytest.fail(f"{job.name}: cron must be an int interval or crontab string")


def test_realtime_market_jobs_are_market_hours_gated() -> None:
    registry = get_brsapi_job_registry()
    for name in _REALTIME_MARKET_JOBS:
        job = registry.get(name)
        assert job is not None, f"{name} is not registered"
        assert job.market_hours_only, f"{name} lost its market-hours gate"


def test_codal_job_uses_wider_office_hours_window() -> None:
    job = get_brsapi_job_registry().get("brsapi_codal")
    assert job is not None
    # Announcements are published after the session, so Codal follows the
    # wider 08:00-18:00 window rather than the trading session.
    assert job.market_hours_only is True
    assert job.codal_window is True


def test_apscheduler_registration_succeeds_with_unique_ids() -> None:
    """Every enabled job registers once, with a distinct APScheduler id."""
    scheduler = AsyncIOScheduler(timezone="Asia/Tehran")
    registry = get_brsapi_job_registry()

    registry.register_with_apscheduler(scheduler)

    ids = [job.id for job in scheduler.get_jobs()]
    assert len(ids) == len(registry.enabled)
    assert len(ids) == len(set(ids)), "APScheduler id collision"
    # Registration does not start the scheduler; nothing should be pending.
    assert scheduler.running is False
