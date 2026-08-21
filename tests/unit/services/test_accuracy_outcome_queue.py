"""Tests for audit S2 — no silent outcome loss in signal accuracy tracking.

Guards that:
  1. Outcomes are queued and flushed in batches (not written per-call).
  2. Queue overflow drops the OLDEST item and counts it in a Prometheus
     counter — never silent.
  3. A failed flush re-queues the batch (order preserved) and increments the
     flush-failure metric — nothing is silently lost.
  4. The background flusher drains the queue periodically and on shutdown.
  5. ``record_outcome`` fails fast outside production when no DB is configured,
     and enqueues (returns ok) when a DB is available.
"""

from __future__ import annotations

import asyncio

import pytest

from services.accuracy_outcome_queue import AccuracyOutcomeQueue, get_accuracy_outcome_queue
from services.signal_accuracy_tracker import SignalAccuracyTracker, SignalOutcome


def _outcome(signal_id: str = "sig-1") -> SignalOutcome:
    return SignalOutcome(
        signal_id=signal_id,
        symbol="SYM",
        market="stock",
        source="rule_based",
        direction="buy",
        timeframe="daily",
        actual_return_pct=2.5,
        direction_correct=True,
        max_profit_pct=4.0,
        max_loss_pct=-1.0,
        hit_target1=False,
        hit_target2=False,
        stopped_out=False,
        entry_price=100.0,
        exit_price=102.5,
        signal_price=100.0,
        signal_strength=0.6,
        signal_confidence=0.7,
        ml_score=0.55,
        rule_score=0.6,
    )


class TestAccuracyOutcomeQueue:
    def test_enqueue_and_pending_count(self) -> None:
        queue = AccuracyOutcomeQueue()
        assert queue.enqueue(_outcome("a")) == 0
        assert queue.enqueue(_outcome("b")) == 0
        assert queue.pending_count() == 2
        assert queue.dropped_total() == 0

    def test_overflow_drops_oldest_and_counts(self) -> None:
        queue = AccuracyOutcomeQueue(maxsize=2)
        queue.enqueue(_outcome("a"))
        queue.enqueue(_outcome("b"))
        dropped = queue.enqueue(_outcome("c"))

        assert dropped == 1
        assert queue.dropped_total() == 1
        assert queue.pending_count() == 2
        stats = queue.stats()
        assert stats["dropped_total"] == 1

    async def test_flush_writes_batch_and_clears(self, monkeypatch) -> None:
        queue = AccuracyOutcomeQueue()
        written: list[list[str]] = []

        async def fake_write(batch) -> int:
            written.append([o.signal_id for o in batch])
            return len(batch)

        monkeypatch.setattr(queue, "_write_batch", fake_write)

        queue.enqueue(_outcome("a"))
        queue.enqueue(_outcome("b"))
        queue.enqueue(_outcome("c"))

        assert await queue.flush() == 3
        assert written == [["a", "b", "c"]]
        assert queue.pending_count() == 0
        assert queue.stats()["flush_ok_total"] == 1
        assert queue.stats()["rows_written_total"] == 3

    async def test_failed_flush_requeues_preserving_order(self, monkeypatch) -> None:
        queue = AccuracyOutcomeQueue()
        written: list[list[str]] = []
        attempts = {"n": 0}

        async def fake_write(batch) -> int:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("db down")
            written.append([o.signal_id for o in batch])
            return len(batch)

        monkeypatch.setattr(queue, "_write_batch", fake_write)

        queue.enqueue(_outcome("a"))
        queue.enqueue(_outcome("b"))

        assert await queue.flush() == 0  # failed -> re-queued, nothing lost
        assert queue.pending_count() == 2
        assert queue.stats()["flush_failed_total"] == 1

        assert await queue.flush() == 2  # retry succeeds
        assert written == [["a", "b"]]  # order preserved

    async def test_start_stop_flusher_drains_periodically(self, monkeypatch) -> None:
        queue = AccuracyOutcomeQueue(flush_interval=0.02)
        flush_calls = {"n": 0}

        async def fake_flush() -> int:
            flush_calls["n"] += 1
            return 0

        monkeypatch.setattr(queue, "flush", fake_flush)

        queue.start()
        await asyncio.sleep(0.1)
        queue.enqueue(_outcome("a"))
        await asyncio.sleep(0.1)
        await queue.stop()  # final flush on shutdown

        assert flush_calls["n"] >= 2  # background ticks + shutdown flush
        assert queue.stats()["flusher_running"] is False


class TestTrackerWiring:
    async def test_record_outcome_enqueues_when_db_available(self, monkeypatch) -> None:
        fresh = AccuracyOutcomeQueue()
        monkeypatch.setattr("services.accuracy_outcome_queue.get_accuracy_outcome_queue", lambda: fresh)
        monkeypatch.setattr("core.database.async_session_factory", object())  # non-None

        tracker = SignalAccuracyTracker()
        result = await tracker.record_outcome(_outcome("sig-1"))

        assert result.success is True
        assert fresh.pending_count() == 1

    async def test_record_outcome_fails_fast_without_db_outside_production(self, monkeypatch) -> None:
        # In tests ENV defaults to development (is_production() == False) and
        # core.database.async_session_factory is None -> must raise loudly.
        monkeypatch.setattr("core.database.async_session_factory", None)

        tracker = SignalAccuracyTracker()
        with pytest.raises(RuntimeError, match="fail-fast outside production"):
            await tracker.record_outcome(_outcome("sig-1"))

    async def test_overflow_returns_fail_with_queue_message(self, monkeypatch) -> None:
        fresh = AccuracyOutcomeQueue(maxsize=1)
        monkeypatch.setattr("services.accuracy_outcome_queue.get_accuracy_outcome_queue", lambda: fresh)
        monkeypatch.setattr("core.database.async_session_factory", object())

        tracker = SignalAccuracyTracker()
        assert (await tracker.record_outcome(_outcome("first"))).success is True
        second = await tracker.record_outcome(_outcome("second"))  # overflows

        assert second.success is False
        assert "overflow" in (second.error or "")
        assert fresh.dropped_total() == 1

    async def test_singleton_is_shared(self) -> None:
        assert get_accuracy_outcome_queue() is get_accuracy_outcome_queue()
