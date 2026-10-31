from __future__ import annotations

import asyncio

from apps.worker.consumer import WorkerConsumer
from apps.worker.error_policy import ErrorPolicy
from core.logging import get_logger

logger = get_logger(__name__)


class WorkerApp:
    def __init__(self) -> None:
        self._running = False
        self.consumer = WorkerConsumer()
        self.error_policy = ErrorPolicy()

    def _register_jobs(self) -> None:
        """Populate the process-local job registries used by the dispatcher.

        Registries are per-process objects. ``SchedulerApp.start`` populates
        them in the scheduler process only, so a worker started on its own
        resolved every queue message to ``Job <name> not found`` and the work
        was retried into the dead-letter queue.
        """
        from brsapi.jobs.registry import register_all_brsapi_jobs
        from jobs import definitions as job_definitions
        from jobs.registry import job_registry

        job_registry.register_module(job_definitions)
        brsapi_registry = register_all_brsapi_jobs()
        logger.info(
            "Worker registered %d job classes and %d BrsApi jobs",
            len(job_registry.list_names()),
            len(brsapi_registry.all),
        )

    async def start(self) -> None:
        self._running = True
        logger.info("Worker started")

        self._register_jobs()

        # Connect Redis in the background so JobQueueConsumer + JobLocking
        # use the distributed backend. Non-blocking: until the connection is
        # ready the consumer idles and the scheduler falls back to in-process.
        try:
            from core.cache import get_cache

            await get_cache().initialize()
        except Exception:
            logger.warning("Redis cache init failed; worker falls back to idle mode")

        await self.consumer.start()
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        await self.consumer.stop()
        logger.info("Worker stopped")
