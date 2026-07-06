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
        self.add_job("SyncQuotesJob", trigger="interval", minutes=5)
        self.add_job("SyncCodalJob", trigger="interval", hours=6)
        self.add_job("NewsIngestionJob", trigger="interval", hours=1)
        self.scheduler.start()
        logger.info("Scheduler started with %d BrsApi jobs", len(register_all_brsapi_jobs().enabled))

    async def run_forever(self) -> None:
        self.start()
        while True:
            await asyncio.sleep(3600)
