from __future__ import annotations

import asyncio
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import settings
from core.logging import get_logger
from jobs.job_dispatcher import job_dispatcher

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
        self.add_job("sync_instruments", trigger="interval", hours=24)
        self.add_job("sync_quotes", trigger="interval", minutes=5)
        self.add_job("sync_codal", trigger="interval", hours=6)
        self.add_job("sync_news", trigger="interval", hours=1)
        self.scheduler.start()
        logger.info("Scheduler started")

    async def run_forever(self) -> None:
        self.start()
        while True:
            await asyncio.sleep(3600)
