from __future__ import annotations

import asyncio
import random

from core.logging import get_logger

logger = get_logger(__name__)


class JobRetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 10.0,
        max_delay: float = 3600.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._backoff_factor = backoff_factor
        self._jitter = jitter
        self._retries: dict[str, int] = {}

    def should_retry(self, job_id: str) -> bool:
        count = self._retries.get(job_id, 0)
        return count < self._max_retries

    def get_delay(self, job_id: str) -> float:
        count = self._retries.get(job_id, 0)
        delay = min(self._base_delay * (self._backoff_factor**count), self._max_delay)
        if self._jitter:
            delay *= 0.5 + random.random() * 0.5
        return delay

    def record_retry(self, job_id: str) -> int:
        count = self._retries.get(job_id, 0) + 1
        self._retries[job_id] = count
        logger.info("Retry %d/%d recorded for job %s", count, self._max_retries, job_id)
        return count

    def clear_retries(self, job_id: str) -> None:
        self._retries.pop(job_id, None)

    def get_retry_count(self, job_id: str) -> int:
        return self._retries.get(job_id, 0)

    async def wait(self, job_id: str) -> None:
        delay = self.get_delay(job_id)
        logger.info("Waiting %.1fs before retry for job %s", delay, job_id)
        await asyncio.sleep(delay)
