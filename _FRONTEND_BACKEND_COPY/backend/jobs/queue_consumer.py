"""Job Queue Consumer — executes jobs pulled from the Redis queue.

Runs inside the dedicated ``worker`` replicas (``apps/worker``).  Each
message published by :class:`jobs.queue_publisher.JobQueuePublisher` is:

1. Popped from ``job:queue`` (``BRPOP`` — round-robin across workers).
2. Auth-verified against the shared token (messages without a valid token
   are dropped and counted).
3. Dispatched through the existing ``job_dispatcher`` (which applies the
   distributed ``JobLocking`` lock so the job runs exactly once even if the
   same message was pushed by multiple scheduler replicas).
4. On hard failure, retried up to ``max_retries`` times via ``job:retry``,
   then moved to ``job:dead`` (dead-letter) for manual inspection.

Fallback / dev mode: when ``JOB_QUEUE_ENABLED=false`` the worker simply
idles; the scheduler executes jobs in-process instead (see docs/job-queue.md).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from contextlib import suppress
from typing import Any

from core.config import settings
from core.logging import get_logger
from jobs.job_context import JobContext

logger = get_logger(__name__)

# Lock/duplicate failures mean "another worker already handled it" — benign.
_BENIGN_ERROR_MARKERS = ("Lock not acquired", "Duplicate")


class JobQueueConsumer:
    """Consume and execute job messages from a Redis-backed queue."""

    def __init__(
        self,
        redis_client: Any | None = None,
        queue_name: str | None = None,
        token: str | None = None,
        dispatcher: Any | None = None,
        max_retries: int = 3,
        poll_timeout: int | None = None,
    ) -> None:
        """
        Parameters
        ----------
        redis_client:
            Optional ``redis.asyncio`` client (defaults to the shared
            ``core.cache.get_cache().client`` connection).
        queue_name:
            Redis list to consume (default ``settings.job_queue_name``).
        token:
            Shared auth token (default ``settings.job_queue_token``; empty
            means *no auth* — dev only).
        dispatcher:
            Callable/object with ``async dispatch(job_name, params, context)``
            (defaults to ``job_dispatcher``).
        max_retries:
            Hard-failure retry budget before moving to the dead-letter queue.
        poll_timeout:
            ``BRPOP`` timeout in seconds (default from settings).
        """
        self._client = redis_client
        self._queue_name = queue_name or settings.job_queue_name
        self._dead_queue = settings.job_queue_dead_letter
        self._token = token if token is not None else settings.job_queue_token
        self._dispatcher = dispatcher
        self._max_retries = max_retries
        self._poll_timeout = poll_timeout if poll_timeout is not None else settings.job_queue_consumer_timeout
        self._lease_seconds = settings.job_queue_lease_seconds
        self._worker_id = uuid.uuid4().hex[:12]
        self._processing_queue = f"{self._queue_name}:processing:{self._worker_id}"
        self._worker_lease_key = f"{self._queue_name}:worker:{self._worker_id}"

        self._running = False
        self._task: asyncio.Task[Any] | None = None

        # Diagnostics
        self.processed = 0
        self.failed = 0
        self.dead_lettered = 0
        self.rejected_auth = 0
        self._started_at: float = 0.0

    # ── Redis plumbing ────────────────────────────────────────────────

    def _redis(self) -> Any | None:
        if self._client is not None:
            return self._client
        try:
            from core.cache import get_cache

            return get_cache().client
        except Exception:
            return None

    @property
    def is_available(self) -> bool:
        return self._redis() is not None

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> None:
        """Begin consuming the queue in the background (no await on stop)."""
        if self._running:
            return
        self._running = True
        self._started_at = time.monotonic()
        self._task = asyncio.create_task(self._consume_loop())
        logger.info(
            "JobQueueConsumer started on %s (dead=%s, auth=%s)",
            self._queue_name,
            self._dead_queue,
            "on" if self._token else "OFF",
        )

    async def stop(self) -> None:
        """Stop consuming and wait for the current iteration to finish."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        client = self._redis()
        if client is not None:
            try:
                await client.delete(self._worker_lease_key)
            except Exception:  # noqa: BLE001
                logger.debug("Could not remove queue worker lease", exc_info=True)
        logger.info("JobQueueConsumer stopped (processed=%d failed=%d)", self.processed, self.failed)

    # ── Main loop ─────────────────────────────────────────────────────

    async def _consume_loop(self) -> None:
        client = self._redis()
        if client is None:
            logger.warning("JobQueueConsumer: Redis unavailable — consumer idle")
            return

        try:
            try:
                await client.set(self._worker_lease_key, "1", ex=self._lease_seconds)
            except TypeError:
                # Small Redis-compatible test clients may expose px only.
                await client.set(self._worker_lease_key, "1", px=self._lease_seconds * 1000)
            await self._recover_orphaned_messages(client)
        except Exception:  # noqa: BLE001
            logger.warning("JobQueueConsumer: orphan recovery unavailable", exc_info=True)

        while self._running:
            try:
                if hasattr(client, "expire"):
                    await client.expire(self._worker_lease_key, self._lease_seconds)
                raw = await self._claim_message(client)
                if raw is None:
                    continue
                try:
                    await self._handle_message(raw)
                finally:
                    await self._ack_message(client, raw)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — keep the loop alive
                logger.error("JobQueueConsumer loop error: %s", e)
                await asyncio.sleep(1)

    async def _claim_message(self, client: Any) -> str | None:
        """Move a message to this worker's processing list before execution.

        ``BRPOPLPUSH`` is the Redis list equivalent of a lease: a crash leaves
        the item in the worker-specific processing list, where a later worker
        can recover it after this worker lease expires. The fallback keeps
        lightweight fake clients and old Redis-compatible clients working.
        """
        if hasattr(client, "brpoplpush"):
            value = await client.brpoplpush(
                self._queue_name,
                self._processing_queue,
                self._poll_timeout,
            )
            if value is None:
                return None
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return str(value)
        result = await client.brpop(self._queue_name, self._poll_timeout)
        if not result:
            return None
        value = result[1]
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    async def _ack_message(self, client: Any, raw: str) -> None:
        if hasattr(client, "lrem"):
            await client.lrem(self._processing_queue, 1, raw)

    async def _recover_orphaned_messages(self, client: Any) -> None:
        """Requeue messages left by workers whose lease has expired."""
        if not hasattr(client, "scan_iter") or not hasattr(client, "rpop"):
            return
        pattern = f"{self._queue_name}:processing:*"
        async for key in client.scan_iter(match=pattern):
            key_text = key.decode() if isinstance(key, bytes) else str(key)
            if key_text == self._processing_queue:
                continue
            worker_id = key_text.rsplit(":", 1)[-1]
            worker_lease = f"{self._queue_name}:worker:{worker_id}"
            if await client.exists(worker_lease):
                continue
            while True:
                raw = await client.rpop(key_text)
                if raw is None:
                    break
                await client.lpush(self._queue_name, raw)
            await client.delete(key_text)
            logger.warning("Recovered orphaned queue messages from %s", key_text)

    async def _handle_message(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.error("JobQueueConsumer: malformed message dropped")
            self.failed += 1
            return

        # ── Auth check ─────────────────────────────────────────────────
        if self._token and payload.get("token") != self._token:
            logger.warning(
                "JobQueueConsumer: rejected message with invalid token (%s)",
                payload.get("job_name", "unknown"),
            )
            self.rejected_auth += 1
            return

        job_name = payload.get("job_name", "")
        params = payload.get("params") or {}
        job_id = payload.get("job_id", "")
        attempt = int(payload.get("attempt", 1))

        if not job_name:
            logger.error("JobQueueConsumer: message without job_name dropped")
            self.failed += 1
            return

        logger.info("Consuming job %s (id=%s attempt=%d)", job_name, job_id, attempt)
        context = JobContext(job_id=job_id or "", job_name=job_name, params=params)

        try:
            result = await self._dispatch(job_name, params, context)
        except Exception as e:  # noqa: BLE001
            logger.error("Job %s crashed: %s", job_name, e)
            error = str(e)
            await self._handle_failure(payload, job_name, error, attempt)
            return

        if result is not None and result.success:
            self.processed += 1
            return

        error = getattr(result, "error", "") or "unknown error"
        # Benign: another worker already ran this job (distributed lock).
        if any(marker in error for marker in _BENIGN_ERROR_MARKERS):
            logger.info("Job %s skipped — already handled elsewhere (%s)", job_name, error)
            self.processed += 1
            return

        await self._handle_failure(payload, job_name, error, attempt)

    async def _dispatch(self, job_name: str, params: dict[str, Any], context: JobContext) -> Any:
        dispatcher = self._dispatcher
        if dispatcher is None:
            from jobs.job_dispatcher import job_dispatcher

            dispatcher = job_dispatcher
        return await dispatcher.dispatch(job_name, params=params, context=context)

    # ── Retry / dead-letter ───────────────────────────────────────────

    async def _handle_failure(self, payload: dict[str, Any], job_name: str, error: str, attempt: int) -> None:
        """Route a hard failure to retry (back into the main queue) or dead-letter."""
        if attempt < self._max_retries:
            await self._requeue(payload, attempt + 1)
            logger.warning("Job %s requeued (attempt %d) — %s", job_name, attempt + 1, error)
        else:
            await self._dead_letter(payload, error)
            logger.error("Job %s dead-lettered after %d attempts: %s", job_name, attempt, error)
        self.failed += 1

    async def _requeue(self, payload: dict[str, Any], attempt: int) -> None:
        """Put the message back on the *main* queue so any worker retries it."""
        client = self._redis()
        if client is None:
            return
        payload["attempt"] = attempt
        await client.lpush(self._queue_name, json.dumps(payload, ensure_ascii=False, default=str))

    async def _dead_letter(self, payload: dict[str, Any], error: str) -> None:
        client = self._redis()
        if client is None:
            return
        payload["error"] = error
        payload["dead_lettered_at"] = time.time()
        await client.lpush(self._dead_queue, json.dumps(payload, ensure_ascii=False, default=str))
        self.dead_lettered += 1

    # ── Diagnostics ───────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return consumer diagnostics."""
        uptime_s = time.monotonic() - self._started_at if self._started_at else 0.0
        return {
            "running": self._running,
            "queue": self._queue_name,
            "processed": self.processed,
            "failed": self.failed,
            "dead_lettered": self.dead_lettered,
            "rejected_auth": self.rejected_auth,
            "uptime_s": round(uptime_s, 1),
        }


# ── Singleton ────────────────────────────────────────────────────────

_consumer: JobQueueConsumer | None = None


def get_job_queue_consumer() -> JobQueueConsumer:
    """Get or create the global JobQueueConsumer singleton."""
    global _consumer
    if _consumer is None:
        _consumer = JobQueueConsumer()
    return _consumer
