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
from jobs.registry import job_registry
from jobs.retry_policy import JobRetryPolicy

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
        # JOB-14: this semaphore limits concurrent dispatches to 10 when the
        # dispatcher is called from multiple async tasks simultaneously (e.g. the
        # HTTP /jobs/dispatch endpoint under load).  It has no effect in the
        # sequential queue consumer (queue_consumer.py processes one job at a time
        # via BRPOP), but it is a correct safeguard for other callers.
        self._semaphore = asyncio.Semaphore(10)

    async def dispatch(
        self, job_name: str, params: dict[str, Any] | None = None, context: JobContext | None = None
    ) -> JobResult:
        # JOB-03: build context and apply dedup + distributed lock BEFORE
        # routing to either registry so BrsApi jobs get the same concurrency
        # controls as standard jobs.
        caller_supplied_context = context is not None
        if context is None:
            context = JobContext(job_id=new_id("job"), job_name=job_name, params=params or {})
        if not caller_supplied_context:
            dedup_key = f"{job_name}:{context.job_id}"
            if await self._deduplicator.is_duplicate(dedup_key):
                logger.warning("Dedup: job %s already dispatched", dedup_key)
                return JobResult.failure("Duplicate job", job_name=job_name)
            await self._deduplicator.mark(dedup_key)

        lock_key = f"job:{job_name}"
        async with self._locking.hold(lock_key, context.job_id) as acquired:
            if not acquired:
                return JobResult.failure(f"Lock not acquired for {job_name}", job_name=job_name)
            try:
                async with self._semaphore:
                    job_class = self._registry.get(job_name)
                    if job_class is None:
                        # BrsApi/GoldDesk jobs in the BrsApi registry are
                        # function-based (no BaseJob class). In queue mode the
                        # worker receives their names from Redis.
                        direct = await self._dispatch_brsapi_direct_job(job_name)
                        if direct is not None:
                            return direct
                        return JobResult.failure(f"Job {job_name} not found", job_name=job_name)
                    job = self._registry.create(job_name)
                    if job is None:
                        return JobResult.failure(f"Could not create job {job_name}", job_name=job_name)
                    context.record_start()
                    result = await job.run(context)
                    if result.success:
                        self._retry_policy.clear_retries(context.job_id)
                    return result
            except Exception as e:
                logger.error("Dispatch error for %s: %s", job_name, e)
                return JobResult.failure(str(e), job_name=job_name)


    async def _dispatch_brsapi_direct_job(self, job_name: str) -> JobResult | None:
        """Run a job registered in the BrsApi job registry.

        The registry is the single source of truth for names published by the
        scheduler, and ``run_job`` is the single execution entry point: it
        applies the market-hours gate, routes direct-function jobs and opens
        its own DB session. Keeping a second, hard-coded allow-list here made
        every non-GoldDesk ``brsapi_*`` job resolve to "not found".

        Returns ``None`` only when the name is unknown to the registry so the
        caller can report it as such.
        """
        from brsapi.jobs.registry import get_brsapi_job_registry

        registry = get_brsapi_job_registry()
        if registry.get(job_name) is None:
            return None

        report = await registry.run_job(job_name)
        if report is None:
            # The gate closed (outside market hours) — not due, not broken.
            return JobResult.skipped_result(job_name=job_name, reason="not due (market-hours gate)")
        if report.success:
            return JobResult.success_result(job_name=job_name, message="Completed")
        return JobResult.failure(report.error or "unknown error", job_name=job_name)

    def list_jobs(self) -> list[str]:
        """Return names of all registered jobs."""
        return self._registry.list_names()


# ── Singleton Instance ──────────────────────────────────
# Used by SchedulerApp, CLI, and other services.
job_dispatcher = JobDispatcher(registry=job_registry)
