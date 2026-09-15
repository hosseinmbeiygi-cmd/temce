"""Job Queue — manages backtest jobs in the background.

Supports:
- Submit backtest job → get job_id
- Check job status → pending/running/completed/failed
- Cancel running job
- Get results when complete
- Retry failed jobs
- Job priority and timeout

Uses in-memory queue by default (no external dependencies).
Can be extended to Redis/Celery for production.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """A single backtest job."""

    job_id: str = ""
    name: str = ""
    status: JobStatus = JobStatus.PENDING
    created_at: float = 0.0
    started_at: float | None = None
    completed_at: float | None = None

    # Input
    job_type: str = "backtest"  # backtest | compare | generate | walk_forward
    params: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # higher = more priority

    # Output
    result: dict[str, Any] | None = None
    error: str | None = None

    # Metadata
    progress_pct: float = 0.0
    progress_message: str = ""
    retry_count: int = 0
    max_retries: int = 2
    timeout_seconds: float = 600.0  # 10 minutes default

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at


class JobQueue:
    """In-memory job queue with async workers.

    Usage:
        queue = JobQueue(max_workers=3)
        await queue.start()

        job_id = await queue.submit(name="SmaCross on فولاد", params={...})
        status = queue.get_status(job_id)
        result = queue.get_result(job_id)

        await queue.cancel(job_id)
        await queue.stop()
    """

    def __init__(
        self,
        max_workers: int = 3,
        max_queue_size: int = 100,
    ) -> None:
        self._max_workers = max_workers
        self._max_queue_size = max_queue_size

        self._jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue[str] | None = None
        self._workers: list[asyncio.Task] = []
        self._handlers: dict[str, Callable] = {}
        self._running = False

    def register_handler(self, job_type: str, handler: Callable) -> None:
        """Register a handler function for a job type."""
        self._handlers[job_type] = handler

    async def start(self) -> None:
        """Start worker tasks."""
        self._queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._running = True
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(task)
        logger.info("Job queue started with %d workers", self._max_workers)

    async def stop(self) -> None:
        """Stop all workers."""
        self._running = False
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Job queue stopped")

    async def submit(
        self,
        name: str = "",
        job_type: str = "backtest",
        params: dict[str, Any] | None = None,
        priority: int = 0,
        timeout_seconds: float = 600.0,
    ) -> str:
        """Submit a job to the queue. Returns job_id."""
        if self._queue is None:
            raise RuntimeError("Job queue not started. Call start() first.")

        if self._queue.qsize() >= self._max_queue_size:
            raise RuntimeError("Job queue is full")

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = Job(
            job_id=job_id,
            name=name,
            job_type=job_type,
            params=params or {},
            priority=priority,
            created_at=time.time(),
            timeout_seconds=timeout_seconds,
        )
        self._jobs[job_id] = job
        await self._queue.put(job_id)
        logger.info("Job submitted: %s [%s] %s", job_id, job_type, name)
        return job_id

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        """Get job status."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        return job.to_dict()

    def get_result(self, job_id: str) -> dict[str, Any] | None:
        """Get job result (only if completed)."""
        job = self._jobs.get(job_id)
        if not job or job.status != JobStatus.COMPLETED:
            return None
        return job.result

    async def cancel(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED):
            return False
        job.status = JobStatus.CANCELLED
        job.completed_at = time.time()
        logger.info("Job cancelled: %s", job_id)
        return True

    def list_jobs(self, status: JobStatus | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """List jobs optionally filtered by status."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]

    def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        return {
            "total_jobs": len(self._jobs),
            "pending": sum(1 for j in self._jobs.values() if j.status == JobStatus.PENDING),
            "running": sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING),
            "completed": sum(1 for j in self._jobs.values() if j.status == JobStatus.COMPLETED),
            "failed": sum(1 for j in self._jobs.values() if j.status == JobStatus.FAILED),
            "cancelled": sum(1 for j in self._jobs.values() if j.status == JobStatus.CANCELLED),
            "queue_size": self._queue.qsize() if self._queue else 0,
            "workers": self._max_workers,
        }

    async def _worker(self, name: str) -> None:
        """Worker loop — picks jobs from queue and executes them."""
        while self._running:
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            job = self._jobs.get(job_id)
            if not job or job.status == JobStatus.CANCELLED:
                continue

            job.status = JobStatus.RUNNING
            job.started_at = time.time()
            logger.info("[%s] Starting job: %s", name, job.job_id)

            handler = self._handlers.get(job.job_type)
            if not handler:
                job.status = JobStatus.FAILED
                job.error = f"No handler for job type: {job.job_type}"
                job.completed_at = time.time()
                continue

            try:
                result = await asyncio.wait_for(
                    handler(job),
                    timeout=job.timeout_seconds,
                )
                job.result = result
                job.status = JobStatus.COMPLETED
                job.progress_pct = 100.0
                job.progress_message = "Done"
            except TimeoutError:
                job.status = JobStatus.FAILED
                job.error = f"Job timed out after {job.timeout_seconds}s"
            except Exception as exc:
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.status = JobStatus.PENDING
                    job.started_at = None
                    logger.warning(
                        "[%s] Job %s failed (retry %d/%d): %s", name, job_id, job.retry_count, job.max_retries, exc
                    )
                    await self._queue.put(job_id)
                else:
                    job.status = JobStatus.FAILED
                    job.error = str(exc)
                    logger.error("[%s] Job %s failed permanently: %s", name, job_id, exc)
            finally:
                job.completed_at = time.time()
                elapsed = job.elapsed_seconds()
                logger.info("[%s] Job %s finished: %s (%.1fs)", name, job_id, job.status.value, elapsed)
