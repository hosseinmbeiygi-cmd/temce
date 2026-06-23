from __future__ import annotations

import asyncio
from typing import Any

from core.ids import new_id
from core.logging import get_logger
from jobs.deduplication import JobDeduplicator
from jobs.job_context import JobContext
from jobs.job_registry import JobRegistry
from jobs.job_result import JobResult
from jobs.locking import JobLocking
from jobs.retry_policy import JobRetryPolicy
from jobs.registry import job_registry

logger = get_logger(__name__)


class JobDispatcher:
    def __init__(
        self,
        registry: JobRegistry,
        locking: JobLocking | None = None,
        retry_policy: JobRetryPolicy | None = None,
        deduplicator: JobDeduplicator | None = None,
    ):
        self._registry = registry
        self._locking = locking or JobLocking()
        self._retry_policy = retry_policy or JobRetryPolicy()
        self._deduplicator = deduplicator or JobDeduplicator()
        self._semaphore = asyncio.Semaphore(10)

    async def dispatch(
        self, job_name: str, params: dict[str, Any] | None = None, context: JobContext | None = None
    ) -> JobResult:
        job_class = self._registry.get(job_name)
        if job_class is None:
            return JobResult.failure(f"Job {job_name} not found", job_name=job_name)
        if context is None:
            context = JobContext(job_id=new_id("job"), job_name=job_name, params=params or {})
        dedup_key = f"{job_name}:{context.job_id}"
        if await self._deduplicator.is_duplicate(dedup_key):
            logger.warning("Dedup: job %s already dispatched", dedup_key)
            return JobResult.failure("Duplicate job", job_name=job_name)
        await self._deduplicator.mark(dedup_key)
        lock_key = f"job:{job_name}"
        if not await self._locking.acquire(lock_key, context.job_id):
            return JobResult.failure(f"Lock not acquired for {job_name}", job_name=job_name)
        try:
            async with self._semaphore:
                job = self._registry.create(job_name)
                if job is None:
                    return JobResult.failure(f"Could not create job {job_name}", job_name=job_name)
                context.record_start()
                result = await job.run(context)
                if result.success:
                    await self._retry_policy.clear_retries(context.job_id)
                return result
        except Exception as e:
            logger.error("Dispatch error for %s: %s", job_name, e)
            return JobResult.failure(str(e), job_name=job_name)
        finally:
            await self._locking.release(lock_key, context.job_id)


    def list_jobs(self) -> list[str]:
        """Return names of all registered jobs."""
        return self._registry.list_names()


# ── Singleton Instance ──────────────────────────────────
# Used by SchedulerApp, CLI, and other services.
job_dispatcher = JobDispatcher(registry=job_registry)
