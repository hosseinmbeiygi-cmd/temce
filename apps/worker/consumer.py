from __future__ import annotations

from typing import Any

from core.logging import get_logger
from jobs.queue_consumer import JobQueueConsumer, get_job_queue_consumer

logger = get_logger(__name__)


class WorkerConsumer:
    """Queue-backed worker consumer.

    Wraps :class:`jobs.queue_consumer.JobQueueConsumer` — when queue mode is
    enabled (``JOB_QUEUE_ENABLED=true``) the worker pulls job messages from
    the shared Redis queue, verifies auth, takes the distributed lock and
    dispatches them. When queue mode is disabled the consumer idles (the
    scheduler runs jobs in-process — dev fallback).
    """

    def __init__(self, consumer: JobQueueConsumer | None = None) -> None:
        self._consumer = consumer

    @property
    def consumer(self) -> JobQueueConsumer:
        if self._consumer is None:
            self._consumer = get_job_queue_consumer()
        return self._consumer

    async def start(self) -> None:
        logger.info("Worker consumer starting")
        if self.consumer.is_available:
            await self.consumer.start()
        else:
            logger.warning(
                "Queue mode disabled or Redis unavailable — worker idle "
                "(scheduler runs jobs in-process; see docs/job-queue.md)"
            )

    async def stop(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()
        logger.info("Worker consumer stopped")
