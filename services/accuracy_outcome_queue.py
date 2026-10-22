"""In-process outcome queue for signal accuracy tracking — audit S2.

``SignalAccuracyTracker.record_outcome`` previously returned ``Result.ok`` with
only a log line when the database was unavailable — accuracy outcomes were
silently lost, which hides evaluation bias in a financial system.

This module fixes that with the audit's option 1 (internal queue + durable
flush) combined with option 2 (metrics, and fail-fast outside production):

- Outcomes are enqueued in O(1) and flushed to the DB in **batches**.
- If a flush fails the batch is **re-queued** — nothing is silently dropped.
- Actual drops (queue overflow) and flush failures are counted in Prometheus
  (``accuracy_tracking_dropped_total`` / ``accuracy_tracking_flush_failed_total``)
  so the failure is always visible on ``/metrics``.
- A background flusher (mirroring the BrsApi usage recorder) drains the queue
  periodically; the app lifespan starts/stops it.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MAXSIZE = 10_000
DEFAULT_FLUSH_BATCH = 200
DEFAULT_FLUSH_INTERVAL = 30.0

# Where a failed flush spills its batch so it survives a process restart.
REDIS_SPILL_KEY = "accuracy:outcomes:pending"
REDIS_SPILL_MAX = 10_000


def _serialize_outcome(outcome: Any) -> str | None:
    """JSON-encode a ``SignalOutcome`` for the Redis spill list."""
    import dataclasses
    import json

    if not dataclasses.is_dataclass(outcome):
        return None
    with contextlib.suppress(TypeError, ValueError):
        return json.dumps(dataclasses.asdict(outcome), ensure_ascii=False, default=str)
    return None


def _deserialize_outcome(raw: Any) -> Any | None:
    """Rebuild a ``SignalOutcome`` spilled by :func:`_serialize_outcome`."""
    import dataclasses
    import json

    with contextlib.suppress(Exception):
        from services.signal_accuracy_tracker import SignalOutcome

        payload = json.loads(raw)
        if isinstance(payload, dict):
            allowed = {field.name for field in dataclasses.fields(SignalOutcome)}
            return SignalOutcome(**{k: v for k, v in payload.items() if k in allowed})
    return None


def _inc_metric(name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
    """Increment a Prometheus counter via the process-wide exporter.

    Never raises — metric plumbing must not break the outcome path.
    """
    with contextlib.suppress(Exception):
        from apps.api.metrics import get_prometheus_exporter

        get_prometheus_exporter().inc(name, labels=labels, value=value)


class AccuracyOutcomeQueue:
    """Bounded in-process queue of ``SignalOutcome`` flushed to the DB in batches."""

    def __init__(
        self,
        maxsize: int = DEFAULT_MAXSIZE,
        flush_batch: int = DEFAULT_FLUSH_BATCH,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
    ) -> None:
        self._queue: deque[Any] = deque()
        self._maxsize = maxsize
        self._flush_batch = flush_batch
        self._flush_interval = flush_interval
        self._task: asyncio.Task | None = None
        self._dropped_total = 0
        self._flush_failed_total = 0
        self._flush_ok_total = 0
        self._rows_written_total = 0
        self._redis_recovered_total = 0

    # ── Introspection ──────────────────────────────────────────────────────

    def pending_count(self) -> int:
        return len(self._queue)

    def dropped_total(self) -> int:
        return self._dropped_total

    def stats(self) -> dict[str, Any]:
        """Runtime statistics for monitoring/admin endpoints."""
        return {
            "pending": self.pending_count(),
            "maxsize": self._maxsize,
            "dropped_total": self._dropped_total,
            "flush_ok_total": self._flush_ok_total,
            "flush_failed_total": self._flush_failed_total,
            "rows_written_total": self._rows_written_total,
            "redis_recovered_total": self._redis_recovered_total,
            "redis_spill_key": REDIS_SPILL_KEY,
            "flush_batch": self._flush_batch,
            "flush_interval_seconds": self._flush_interval,
            "flusher_running": self._task is not None and not self._task.done(),
        }

    # ── Enqueue ────────────────────────────────────────────────────────────

    def enqueue(self, outcome: Any) -> int:
        """Append an outcome; returns number of dropped items (0 normally).

        On overflow the oldest pending outcome is dropped and
        ``accuracy_tracking_dropped_total`` is incremented — never silent.
        """
        dropped = 0
        if len(self._queue) >= self._maxsize:
            self._queue.popleft()
            dropped = 1
            self._dropped_total += 1
            _inc_metric("accuracy_tracking_dropped_total", {"reason": "queue_overflow"})
        self._queue.append(outcome)
        return dropped

    # ── Flush ──────────────────────────────────────────────────────────────

    async def flush(self) -> int:
        """Write all pending outcomes in one batched transaction.

        On failure the batch is re-queued (order preserved) and
        ``accuracy_tracking_flush_failed_total`` is incremented. Returns the
        number of rows written; never raises.
        """
        if not self._queue:
            return 0

        batch = self._queue
        self._queue = deque()

        try:
            n = await self._write_batch(batch)
            self._flush_ok_total += 1
            self._rows_written_total += n
            return n
        except Exception as exc:  # noqa: BLE001 — retry later, never drop silently
            for item in reversed(batch):
                self._queue.appendleft(item)  # preserve original FIFO order
            self._flush_failed_total += 1
            _inc_metric("accuracy_tracking_flush_failed_total")
            # In-memory re-queue alone loses the batch if the process dies
            # before the next flush; spill a copy to Redis so it survives.
            await self._spill_to_redis(batch)
            logger.error(
                "Accuracy outcome flush failed for %d items (re-queued): %s",
                len(batch),
                exc,
            )
            return 0

    # ── Durable spill / recovery ───────────────────────────────────────────

    @staticmethod
    def _redis() -> tuple[Any, Any]:
        """Return ``(cache, client)`` when Redis is usable, else ``(None, None)``."""
        with contextlib.suppress(Exception):
            from core.cache import get_cache

            cache = get_cache()
            client = getattr(cache, "client", None)
            if getattr(cache, "is_connected", False) and client is not None:
                return cache, client
        return None, None

    async def _spill_to_redis(self, batch: deque[Any]) -> int:
        """Push a failed batch onto the Redis spill list (best effort)."""
        _, client = self._redis()
        if client is None:
            return 0
        payloads = [raw for raw in (_serialize_outcome(item) for item in batch) if raw]
        if not payloads:
            return 0
        try:
            await client.rpush(REDIS_SPILL_KEY, *payloads)
            await client.ltrim(REDIS_SPILL_KEY, -REDIS_SPILL_MAX, -1)
            return len(payloads)
        except Exception as exc:  # noqa: BLE001 — durability is best effort
            logger.warning("Could not spill %d outcomes to Redis: %s", len(payloads), exc)
            return 0

    async def recover_from_redis(self) -> int:
        """Re-queue outcomes spilled by an earlier failed flush.

        Called once when the flusher starts, so a restart after a DB outage
        drains the backlog instead of losing it. Returns how many outcomes
        were restored (0 when Redis or the spill list is unavailable).
        """
        _, client = self._redis()
        if client is None:
            logger.debug("Outcome recovery skipped: Redis unavailable")
            return 0

        try:
            raw_items = await client.lrange(REDIS_SPILL_KEY, 0, -1)
            if not raw_items:
                return 0
            await client.delete(REDIS_SPILL_KEY)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Outcome recovery from Redis failed: %s", exc)
            return 0

        restored_items = [
            outcome
            for outcome in (_deserialize_outcome(raw) for raw in raw_items)
            if outcome is not None
        ]
        if not restored_items:
            return 0

        # Spilled items predate everything queued since the failure, so they go
        # back on the front in their original order.
        self._queue.extendleft(reversed(restored_items))
        while len(self._queue) > self._maxsize:
            self._queue.popleft()
            self._dropped_total += 1
            _inc_metric("accuracy_tracking_dropped_total", {"reason": "queue_overflow"})

        restored = len(restored_items)
        self._redis_recovered_total += restored
        if restored:
            logger.info("Recovered %d accuracy outcomes spilled to Redis", restored)
        return restored

    async def _write_batch(self, batch: deque[Any]) -> int:
        """Persist a batch of outcomes inside a single transaction."""
        from datetime import UTC, datetime

        from sqlalchemy import text

        from core.database import async_session_factory
        from core.ids import new_id

        if async_session_factory is None:
            raise RuntimeError("No database session factory available")

        now = datetime.now(UTC).replace(tzinfo=None)  # DB column is TIMESTAMP WITHOUT TZ
        written = 0
        async with async_session_factory() as session:
            for outcome in batch:
                # SRV-005: the queue is flushed on a timer and re-queued on
                # failure, so the same outcome can reach this method twice
                # (retry after a partially applied batch, or two workers
                # racing). An unconditional INSERT would then double-count the
                # signal in every accuracy aggregate.
                result = await session.execute(
                    text(
                        "INSERT INTO signal_accuracy ("
                        "id, signal_id, symbol, market, source,"
                        "direction, timeframe,"
                        "actual_return_pct, direction_correct,"
                        "max_profit_pct, max_loss_pct,"
                        "hit_target1, hit_target2, stopped_out,"
                        "entry_price, exit_price, signal_price,"
                        "signal_strength, signal_confidence,"
                        "ml_score, rule_score,"
                        "generated_at, outcome_set_at"
                        ") SELECT "
                        ":id, :signal_id, :symbol, :market, :source,"
                        ":direction, :timeframe,"
                        ":actual_return_pct, :direction_correct,"
                        ":max_profit_pct, :max_loss_pct,"
                        ":hit_target1, :hit_target2, :stopped_out,"
                        ":entry_price, :exit_price, :signal_price,"
                        ":signal_strength, :signal_confidence,"
                        ":ml_score, :rule_score,"
                        ":generated_at, :outcome_set_at"
                        " WHERE NOT EXISTS ("
                        "SELECT 1 FROM signal_accuracy WHERE signal_id = :signal_id"
                        ")"
                    ),
                    {
                        "id": new_id("sacc"),
                        "signal_id": outcome.signal_id,
                        "symbol": outcome.symbol,
                        "market": outcome.market,
                        "source": outcome.source,
                        "direction": outcome.direction,
                        "timeframe": outcome.timeframe,
                        "actual_return_pct": outcome.actual_return_pct,
                        "direction_correct": outcome.direction_correct,
                        "max_profit_pct": outcome.max_profit_pct,
                        "max_loss_pct": outcome.max_loss_pct,
                        "hit_target1": outcome.hit_target1,
                        "hit_target2": outcome.hit_target2,
                        "stopped_out": outcome.stopped_out,
                        "entry_price": outcome.entry_price,
                        "exit_price": outcome.exit_price,
                        "signal_price": outcome.signal_price,
                        "signal_strength": outcome.signal_strength,
                        "signal_confidence": outcome.signal_confidence,
                        "ml_score": outcome.ml_score,
                        "rule_score": outcome.rule_score,
                        "generated_at": now,
                        "outcome_set_at": now,
                    },
                )
                written += result.rowcount or 0
            await session.commit()
        return written

    # ── Background flusher ─────────────────────────────────────────────────

    def start(self) -> None:
        """Start the periodic background flusher (idempotent)."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_flusher())

    async def stop(self) -> None:
        """Stop the flusher and flush whatever is still pending."""
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self.flush()

    async def _run_flusher(self) -> None:
        with contextlib.suppress(Exception):
            await self.recover_from_redis()
        while True:
            await asyncio.sleep(self._flush_interval)
            try:
                await self.flush()
            except Exception:  # noqa: BLE001
                logger.exception("Accuracy outcome flusher error")


_singleton: AccuracyOutcomeQueue | None = None


def get_accuracy_outcome_queue() -> AccuracyOutcomeQueue:
    """Return the shared process-wide outcome queue."""
    global _singleton
    if _singleton is None:
        _singleton = AccuracyOutcomeQueue()
    return _singleton
