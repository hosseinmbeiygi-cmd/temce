from __future__ import annotations

import asyncio
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.logging import get_logger
from jobs import definitions as job_definitions
from jobs.job_dispatcher import job_dispatcher
from jobs.registry import job_registry

logger = get_logger(__name__)


class SchedulerApp:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)

    def add_job(self, job_name: str, trigger: str = "interval", **kwargs: Any) -> None:
        async def wrapper() -> None:
            logger.info("Scheduler running job: %s", job_name)
            await job_dispatcher.dispatch(job_name)

        self.scheduler.add_job(wrapper, trigger, **kwargs)
        logger.info("Scheduled job %s with %s", job_name, trigger)

    def start(self) -> None:
        # ── Register all job classes so dispatcher can find them ──
        job_registry.register_module(job_definitions)

        # ── BrsApi periodic sync jobs (registered via dedicated registry) ──
        from brsapi.jobs.registry import register_all_brsapi_jobs
        register_all_brsapi_jobs().register_with_apscheduler(self.scheduler)

        # ── Legacy sync jobs (now proper BaseJob classes with DB sessions) ──
        self.add_job("SyncInstrumentsJob", trigger="interval", hours=24)
        self.add_job("SyncQuotesJob", trigger="interval", minutes=2)
        self.add_job("SyncSnapshotsToQuotesJob", trigger="interval", minutes=2)
        self.add_job("SyncCodalJob", trigger="interval", hours=6)
        self.add_job(
            "CodalAttachmentDownloadJob",
            trigger="interval",
            minutes=15,
            max_instances=1,
            replace_existing=True,
        )
        self.add_job("SyncNavAllJob", trigger="cron", hour=9, minute=0, max_instances=1, replace_existing=True)
        self.add_job("NewsIngestionJob", trigger="interval", minutes=10)

        # ── Evaluate user price/volume/RSI alerts against live data ──
        # Runs every 2 minutes so alerts fire shortly after the condition holds.
        self.add_job("EvaluateAlertsJob", trigger="interval", minutes=2, max_instances=1, replace_existing=True)

        # ── Backfill historical data (daily, off-peak hours) ──
        self.add_job(
            "BackfillHistoricalDataJob",
            trigger="cron",
            hour=2,          # Run at 2 AM Tehran time
            minute=0,
            max_instances=1,  # Never run two backfills concurrently
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("Scheduler started with %d BrsApi jobs", len(register_all_brsapi_jobs().enabled))

    async def run_forever(self) -> None:
        # Init Redis cache in the background so JobLocking uses the
        # distributed (Redis) lock in this process instead of the
        # single-process in-memory fallback. Non-blocking: until the
        # connection is ready, JobLocking degrades to in-memory locking.
        try:
            from core.cache import get_cache

            asyncio.create_task(get_cache().initialize())
        except Exception:
            logger.warning("Redis cache init failed; scheduler falls back to in-memory locks")
        self.start()
        while True:
            await asyncio.sleep(3600)
