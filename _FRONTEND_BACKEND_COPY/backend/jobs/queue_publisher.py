"""Job Queue Publisher — pushes scheduled jobs into a Redis queue.

Architecture
------------
With multiple FastAPI replicas under Docker Swarm every replica runs its own
APScheduler, so the same job would fire N times.  The fix is to make the
scheduler *only push* job messages into a shared Redis queue (``job:queue``)
and let dedicated ``worker`` replicas consume + execute them exactly once
(protected by the distributed lock in ``jobs.locking``).

This module implements the producer side:

    scheduler (cron fires)
        └── JobQueuePublisher.publish(job_name, params)
                └── LPUSH job:queue  {job_name, params, job_id, token, ...}

The payload carries a shared auth token so a worker can verify the message
really came from our scheduler (see ``jobs/queue_consumer.py``).

Fallback
--------
When Redis is unavailable (or ``JOB_QUEUE_ENABLED=false``) callers keep using
the existing in-process ``job_dispatcher`` — see ``docs/job-queue.md``.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import Any

from core.config import settings
from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)


class JobQueuePublisher:
    """Publish job messages to a Redis-backed queue (``LPUSH``)."""

    def __init__(
        self,
        redis_client: Any | None = None,
        queue_name: str | None = None,
        token: str | None = None,
    ) -> None:
        """
        Parameters
        ----------
        redis_client:
            Optional ``redis.asyncio`` client. Defaults to the shared
            connection from ``core.cache.get_cache().client``.
        queue_name:
            Redis list used as the queue (default ``settings.job_queue_name``).
        token:
            Shared auth token embedded in every message (default
            ``settings.job_queue_token``; a random per-process token is
            generated when unset — fine for dev, set it in production).
        """
        self._client = redis_client
        self._queue_name = queue_name or settings.job_queue_name
        self._token = token if token is not None else (settings.job_queue_token or secrets.token_urlsafe(16))

    # ── Redis plumbing ────────────────────────────────────────────────

    def _redis(self) -> Any | None:
        """Return the connected redis client, or None when unavailable."""
        if self._client is not None:
            return self._client
        try:
            from core.cache import get_cache

            return get_cache().client
        except Exception:
            return None

    @property
    def is_available(self) -> bool:
        """True when a Redis client is reachable (queue mode usable)."""
        return self._redis() is not None

    # ── Public API ────────────────────────────────────────────────────

    async def publish(
        self,
        job_name: str,
        params: dict[str, Any] | None = None,
        ttl: int | None = None,
    ) -> str | None:
        """Push a job message onto the queue.

        Returns the message id, or ``None`` when Redis is unavailable
        (callers should fall back to in-process dispatch).
        """
        client = self._redis()
        if client is None:
            logger.warning(
                "JobQueuePublisher: Redis unavailable — cannot enqueue %s",
                job_name,
            )
            return None

        payload = {
            "type": "job",
            "job_name": job_name,
            "params": params or {},
            "job_id": new_id("job"),
            "token": self._token,
            "ttl": ttl or settings.job_queue_lock_ttl,
            "published_at": datetime.now(UTC).isoformat(),
        }
        serialized = json.dumps(payload, ensure_ascii=False, default=str)

        try:
            await client.lpush(self._queue_name, serialized)
            logger.info("Published job %s to %s (%s)", job_name, self._queue_name, payload["job_id"])
            return payload["job_id"]
        except Exception as e:  # noqa: BLE001 — queue must never crash the scheduler
            logger.error("Failed to publish job %s to %s: %s", job_name, self._queue_name, e)
            return None

    async def queue_size(self) -> int:
        """Current number of messages in the queue (0 when Redis is down)."""
        client = self._redis()
        if client is None:
            return 0
        try:
            return int(await client.llen(self._queue_name) or 0)
        except Exception:  # noqa: BLE001
            return 0


# ── Singleton ────────────────────────────────────────────────────────

_publisher: JobQueuePublisher | None = None


def get_job_queue_publisher() -> JobQueuePublisher:
    """Get or create the global JobQueuePublisher singleton."""
    global _publisher
    if _publisher is None:
        _publisher = JobQueuePublisher()
    return _publisher
