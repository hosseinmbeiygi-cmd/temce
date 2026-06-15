from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScheduledJob:
    job_id: str
    job_name: str
    cron_expression: str
    kwargs: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


JobFunc = Callable[..., Coroutine[Any, Any, Any]]


class JobScheduler:
    def __init__(self) -> None:
        self._scheduled: dict[str, ScheduledJob] = {}
        self._job_funcs: dict[str, JobFunc] = {}
        self._running = False
        self._id_counter = 0

    def schedule_job(self, job_name: str, cron_expression: str, **kwargs: Any) -> ScheduledJob:
        self._id_counter += 1
        job_id = f"sched-{self._id_counter:06d}"
        scheduled = ScheduledJob(
            job_id=job_id,
            job_name=job_name,
            cron_expression=cron_expression,
            kwargs=kwargs,
        )
        self._scheduled[job_id] = scheduled
        logger.info(
            "Scheduled job %s with cron %s (id=%s)",
            job_name,
            cron_expression,
            job_id,
        )
        return scheduled

    def unschedule_job(self, job_id: str) -> bool:
        if job_id in self._scheduled:
            del self._scheduled[job_id]
            logger.info("Unscheduled job %s", job_id)
            return True
        return False

    def list_scheduled_jobs(self) -> list[ScheduledJob]:
        return list(self._scheduled.values())

    def get_scheduled_job(self, job_id: str) -> ScheduledJob | None:
        return self._scheduled.get(job_id)

    def enable_job(self, job_id: str) -> bool:
        job = self._scheduled.get(job_id)
        if job:
            job.enabled = True
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        job = self._scheduled.get(job_id)
        if job:
            job.enabled = False
            return True
        return False

    def register_job_func(self, job_name: str, func: JobFunc) -> None:
        self._job_funcs[job_name] = func
        logger.info("Registered job function: %s", job_name)

    async def run_job_now(self, job_id: str) -> Any:
        job = self._scheduled.get(job_id)
        if job is None:
            logger.warning("Scheduled job %s not found", job_id)
            return None
        func = self._job_funcs.get(job.job_name)
        if func is None:
            logger.warning("No function registered for job %s", job.job_name)
            return None
        job.last_run = datetime.now(UTC)
        logger.info("Running scheduled job %s now", job.job_name)
        try:
            result = await func(**job.kwargs)
            return result
        except Exception as e:
            logger.error("Failed to run scheduled job %s: %s", job.job_name, e)
            return None

    def start(self) -> None:
        self._running = True
        logger.info("Job scheduler started")

    def stop(self) -> None:
        self._running = False
        logger.info("Job scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_scheduled": len(self._scheduled),
            "enabled": sum(1 for j in self._scheduled.values() if j.enabled),
            "disabled": sum(1 for j in self._scheduled.values() if not j.enabled),
            "running": self._running,
            "registered_funcs": list(self._job_funcs.keys()),
        }


scheduler = JobScheduler()
