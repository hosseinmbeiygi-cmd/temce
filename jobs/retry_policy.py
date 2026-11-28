"""Retry bookkeeping that survives worker restarts when Redis is available
(audit F11, 2026-11-28).

Previously the counters lived in a plain dict on the policy instance: a worker
restart silently reset them (a crash-looping job then retried forever) and two
workers counted independently. Counters now live in Redis
(``job:retry:count:<key>``, 24h TTL) with the old in-memory dict as the no-Redis
fallback. All reading/mutating methods are async — the queue consumer and the
dispatcher await them.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class JobRetryPolicy:
    REDIS_PREFIX = "job:retry:count:"
    REDIS_TTL_SECONDS = 86400

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 10.0,
        max_delay: float = 3600.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        redis_client: Any | None = None,
    ):
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._backoff_factor = backoff_factor
        self._jitter = jitter
        # Explicit override for tests; otherwise the shared cache client is used.
        self._redis_override = redis_client
        self._retries: dict[str, int] = {}

    def _client(self) -> Any | None:
        if self._redis_override is not None:
            return self._redis_override
        try:
            from core.cache import get_cache

            return get_cache().client
        except Exception:
            return None

    async def _count(self, job_id: str) -> int:
        client = self._client()
        if client is not None:
            try:
                return int(await client.get(f"{self.REDIS_PREFIX}{job_id}") or 0)
            except Exception as e:
                logger.warning("Retry count read failed for %s; using in-memory fallback: %s", job_id, e)
        return self._retries.get(job_id, 0)

    async def should_retry(self, job_id: str) -> bool:
        count = await self._count(job_id)
        return count < self._max_retries

    async def record_retry(self, job_id: str) -> int:
        client = self._client()
        if client is not None:
            try:
                key = f"{self.REDIS_PREFIX}{job_id}"
                count = int(await client.incr(key))
                await client.expire(key, self.REDIS_TTL_SECONDS)
                self._retries.pop(job_id, None)
                logger.info("Retry %d/%d recorded for job %s (redis)", count, self._max_retries, job_id)
                return count
            except Exception as e:
                logger.warning("Retry record failed for %s; using in-memory fallback: %s", job_id, e)
        count = self._retries.get(job_id, 0) + 1
        self._retries[job_id] = count
        logger.info("Retry %d/%d recorded for job %s (in-memory)", count, self._max_retries, job_id)
        return count

    async def clear_retries(self, job_id: str) -> None:
        """Reset the counter after a success — in Redis too, or a same-day failure
        would inherit the pre-success attempts and dead-letter early."""
        self._retries.pop(job_id, None)
        client = self._client()
        if client is None:
            return
        try:
            await client.delete(f"{self.REDIS_PREFIX}{job_id}")
        except Exception as e:
            logger.warning("Retry clear failed for %s: %s", job_id, e)

    def get_delay(self, job_id: str) -> float:
        """Delay for a *recorded in-memory* count. Kept for callers/tests building
        delays from the fallback dict; wait() computes from the live counter."""
        count = self._retries.get(job_id, 0)
        delay = min(self._base_delay * (self._backoff_factor ** count), self._max_delay)
        if self._jitter:
            delay *= 0.5 + random.random() * 0.5
        return delay

    async def wait(self, job_id: str) -> None:
        count = await self._count(job_id)
        delay = min(self._base_delay * (self._backoff_factor ** count), self._max_delay)
        if self._jitter:
            delay *= 0.5 + random.random() * 0.5
        logger.info("Waiting %.1fs before retry for job %s", delay, job_id)
        await asyncio.sleep(delay)
