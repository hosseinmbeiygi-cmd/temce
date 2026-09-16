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
            logger.error(
                "Accuracy outcome flush failed for %d items (re-queued): %s",
                len(batch),
                exc,
            )
            return 0

    async def _write_batch(self, batch: deque[Any]) -> int:
        """Persist a batch of outcomes inside a single transaction."""
        from datetime import UTC, datetime

        from sqlalchemy import text

        from core.database import async_session_factory
        from core.ids import new_id

        if async_session_factory is None:
            raise RuntimeError("No database session factory available")

        now = datetime.now(UTC).replace(tzinfo=None)  # DB column is TIMESTAMP WITHOUT TZ
        async with async_session_factory() as session:
            for outcome in batch:
                await session.execute(
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
                        ") VALUES ("
                        ":id, :signal_id, :symbol, :market, :source,"
                        ":direction, :timeframe,"
                        ":actual_return_pct, :direction_correct,"
                        ":max_profit_pct, :max_loss_pct,"
                        ":hit_target1, :hit_target2, :stopped_out,"
                        ":entry_price, :exit_price, :signal_price,"
                        ":signal_strength, :signal_confidence,"
                        ":ml_score, :rule_score,"
                        ":generated_at, :outcome_set_at"
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
            await session.commit()
        return len(batch)

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
