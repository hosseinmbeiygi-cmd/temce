from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class ScheduledJob:
    def __init__(self, name: str, callback: Callable, interval_seconds: int, max_runs: int = 0) -> None:
        self.name = name
        self.callback = callback
        self.interval_seconds = interval_seconds
        self.max_runs = max_runs
        self.run_count: int = 0
        self.last_run: datetime | None = None
        self.enabled: bool = True

    def should_run(self) -> bool:
        if not self.enabled:
            return False
        if self.max_runs > 0 and self.run_count >= self.max_runs:
            return False
        if self.last_run is None:
            return True
        elapsed = (datetime.now(UTC) - self.last_run).total_seconds()
        return elapsed >= self.interval_seconds


class ScrapeScheduler:
    def __init__(self) -> None:
        self._jobs: list[ScheduledJob] = []
        self._running: bool = False
        self._task: asyncio.Task | None = None

    def add_job(self, job: ScheduledJob) -> None:
        self._jobs.append(job)
        logger.info("Scheduled job added: %s (every %ds)", job.name, job.interval_seconds)

    def remove_job(self, name: str) -> None:
        self._jobs = [j for j in self._jobs if j.name != name]

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scrape scheduler started with %d jobs", len(self._jobs))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Scrape scheduler stopped")

    async def _run_loop(self) -> None:
        while self._running:
            for job in self._jobs:
                if job.should_run():
                    try:
                        jitter = random.uniform(0, 5)
                        await asyncio.sleep(jitter)
                        await job.callback()
                        job.run_count += 1
                        job.last_run = datetime.now(UTC)
                        logger.debug("Job %s completed (run %d)", job.name, job.run_count)
                    except Exception as e:
                        logger.error("Job %s failed: %s", job.name, e)
            await asyncio.sleep(1)

    def get_status(self) -> list[dict[str, Any]]:
        return [
            {
                "name": j.name,
                "interval": j.interval_seconds,
                "run_count": j.run_count,
                "last_run": j.last_run.isoformat() if j.last_run else None,
                "enabled": j.enabled,
            }
            for j in self._jobs
        ]

    async def health(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "jobs": len(self._jobs),
            "active_jobs": sum(1 for j in self._jobs if j.enabled),
        }
