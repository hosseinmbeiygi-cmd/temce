"""Signal Accuracy Tracker — records signal outcomes and computes accuracy metrics by market / source / symbol.

After a signal's prediction period ends, the tracker checks what actually happened
and records: direction_correct, max_profit, max_loss, stop-out, target hits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from core.logging import get_logger
from core.result import PaginatedResult, Result

logger = get_logger(__name__)


@dataclass
class SignalOutcome:
    """Result of evaluating a signal after its prediction period."""
    signal_id: str
    symbol: str
    market: str
    source: str
    direction: str
    timeframe: str

    actual_return_pct: float
    direction_correct: bool
    max_profit_pct: float
    max_loss_pct: float
    hit_target1: bool
    hit_target2: bool
    stopped_out: bool
    entry_price: float
    exit_price: float
    signal_price: float
    signal_strength: float
    signal_confidence: float
    ml_score: float | None = None
    rule_score: float | None = None


class SignalAccuracyTracker:
    """Tracks and computes accuracy metrics for generated signals."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def record_outcome(self, outcome: SignalOutcome) -> Result[str]:
        """Record the outcome of a single signal after its period ends.

        Audit S2 (no silent failures): outcomes are enqueued and flushed to the
        DB in batches by the background flusher. If the queue overflows the
        drop is counted in Prometheus (``accuracy_tracking_dropped_total``).
        Outside production a missing database raises loudly instead of silently
        acknowledging the outcome.
        """
        from core.config import settings
        from core.database import async_session_factory
        from services.accuracy_outcome_queue import get_accuracy_outcome_queue

        if async_session_factory is None and not settings.is_production:
            raise RuntimeError(
                "No database session available for accuracy tracking (audit S2): "
                "fail-fast outside production — outcomes must never be silently dropped"
            )
        try:
            dropped = get_accuracy_outcome_queue().enqueue(outcome)
            if dropped:
                logger.error(
                    "Accuracy outcome queue overflow — dropped oldest outcome for signal %s",
                    outcome.signal_id,
                )
                return Result.fail("accuracy outcome queue overflow")
            logger.info(
                "Queued outcome for signal %s: correct=%s return=%.2f%%",
                outcome.signal_id, outcome.direction_correct, outcome.actual_return_pct,
            )
            return Result.ok(outcome.signal_id)
        except Exception as e:
            logger.error("Failed to record signal outcome: %s", e)
            return Result.fail(str(e))

    async def evaluate_signal(
        self,
        signal: dict[str, Any],
        entry_price: float,
        exit_price: float,
        high_price: float | None = None,
        low_price: float | None = None,
        target1: float | None = None,
        target2: float | None = None,
        stop_loss: float | None = None,
    ) -> SignalOutcome:
        """Evaluate a signal against actual price movement."""
        direction = signal.get("direction", "hold")
        signal_price = signal.get("price", entry_price)

        # Compute actual return
        # Use >= / <= so a zero-move (flat market, very common for currency/
        # gold) counts as correct instead of False — strict > penalized flat
        # signals and dragged recorded accuracy toward zero.
        if entry_price <= 0:
            # Un-evaluable (guard division-by-zero on degenerate input)
            actual_return = 0.0
            direction_correct = False
        elif direction == "buy":
            actual_return = ((exit_price - entry_price) / entry_price) * 100
            direction_correct = exit_price >= entry_price
        elif direction == "sell":
            actual_return = ((entry_price - exit_price) / entry_price) * 100
            direction_correct = exit_price <= entry_price
        else:  # hold
            actual_return = 0.0
            direction_correct = True  # hold is always "correct" in neutral terms

        # Max profit / loss during period
        max_profit = 0.0
        max_loss = 0.0
        if high_price and low_price:
            if direction == "buy":
                max_profit = ((high_price - entry_price) / entry_price) * 100
                max_loss = ((entry_price - low_price) / entry_price) * 100
            elif direction == "sell":
                max_profit = ((entry_price - low_price) / entry_price) * 100
                max_loss = ((high_price - entry_price) / entry_price) * 100

        # Target hits
        hit_t1 = False
        hit_t2 = False
        if target1 is not None:
            if direction == "buy" and high_price and high_price >= target1 or direction == "sell" and low_price and low_price <= target1:
                hit_t1 = True
        if target2 is not None:
            if direction == "buy" and high_price and high_price >= target2 or direction == "sell" and low_price and low_price <= target2:
                hit_t2 = True

        # Stop-out check
        stopped = False
        if stop_loss is not None:
            if direction == "buy" and low_price and low_price <= stop_loss or direction == "sell" and high_price and high_price >= stop_loss:
                stopped = True

        return SignalOutcome(
            signal_id=signal.get("id", ""),
            symbol=signal.get("symbol", ""),
            market=signal.get("market", ""),
            source=signal.get("source", "rule_based"),
            direction=direction,
            timeframe=signal.get("timeframe", "daily"),
            actual_return_pct=actual_return,
            direction_correct=direction_correct,
            max_profit_pct=max_profit,
            max_loss_pct=max_loss,
            hit_target1=hit_t1,
            hit_target2=hit_t2,
            stopped_out=stopped,
            entry_price=entry_price,
            exit_price=exit_price,
            signal_price=signal_price,
            signal_strength=signal.get("strength", 0.0),
            signal_confidence=signal.get("confidence", 0.0),
            ml_score=signal.get("ml_score"),
            rule_score=signal.get("rule_score"),
        )

    async def get_accuracy_by_market(
        self,
        market: str | None = None,
        days: int = 30,
        page: int = 1,
        page_size: int = 50,
    ) -> Result[PaginatedResult[dict[str, Any]]]:
        """Get accuracy metrics grouped by market and source."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                self._count_unavailable_read()
                return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))

            async with async_session_factory() as session:
                cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

                # Only buy/sell signals have a tradable outcome; hold/wait rows
                # are recorded as "always correct" and would otherwise inflate
                # accuracy (e.g. IME showing 100% from holds).
                where_clause = "WHERE outcome_set_at >= :cutoff AND direction IN ('buy', 'sell')"
                params: dict[str, Any] = {"cutoff": cutoff}
                if market:
                    where_clause += " AND market = :market"
                    params["market"] = market

                r = await session.execute(text(f"""
                    SELECT market, source,
                           COUNT(*) as total,
                           SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END) as correct,
                           AVG(actual_return_pct) as avg_return,
                           AVG(max_profit_pct) as avg_max_profit,
                           AVG(max_loss_pct) as avg_max_loss,
                           SUM(CASE WHEN hit_target1 THEN 1 ELSE 0 END) as target1_hits,
                           SUM(CASE WHEN stopped_out THEN 1 ELSE 0 END) as stop_outs
                    FROM signal_accuracy
                    {where_clause}
                    GROUP BY market, source
                    ORDER BY SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END) * 1.0 / NULLIF(MAX(COUNT(*)) OVER (PARTITION BY market), 0) DESC
                """), params)
                rows = r.fetchall()

                items = []
                for row in rows:
                    total = row[2] or 0
                    correct = row[3] or 0
                    items.append({
                        "market": row[0],
                        "source": row[1],
                        "total": total,
                        "correct": correct,
                        "accuracy_pct": round((correct / max(total, 1)) * 100, 2),
                        "avg_return_pct": round(row[4] or 0, 2),
                        "avg_max_profit_pct": round(row[5] or 0, 2),
                        "avg_max_loss_pct": round(row[6] or 0, 2),
                        "target1_hit_rate_pct": round(((row[7] or 0) / max(total, 1)) * 100, 2),
                        "stop_out_rate_pct": round(((row[8] or 0) / max(total, 1)) * 100, 2),
                    })

                return Result.ok(PaginatedResult(
                    items=items, total=len(items), page=page, page_size=page_size,
                    total_pages=max(1, (len(items) + page_size - 1) // page_size),
                ))
        except Exception as e:
            logger.error("Failed to get accuracy by market: %s", e)
            self._count_unavailable_read(reason="error")
            return Result.ok(PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=1))

    async def get_accuracy_by_symbol(
        self,
        symbol: str,
        days: int = 90,
    ) -> Result[dict[str, Any]]:
        """Get accuracy metrics for a specific symbol."""
        try:
            from sqlalchemy import text

            from core.database import async_session_factory

            if async_session_factory is None:
                self._count_unavailable_read()
                return Result.ok({"symbol": symbol, "total": 0, "accuracy_pct": 0})

            async with async_session_factory() as session:
                cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)

                r = await session.execute(text("""
                    SELECT source, direction,
                           COUNT(*) as total,
                           SUM(CASE WHEN direction_correct THEN 1 ELSE 0 END) as correct,
                           AVG(actual_return_pct) as avg_return
                    FROM signal_accuracy
                    WHERE symbol = :symbol AND outcome_set_at >= :cutoff
                      AND direction IN ('buy', 'sell')
                    GROUP BY source, direction
                    ORDER BY total DESC
                """), {"symbol": symbol, "cutoff": cutoff})
                rows = r.fetchall()

                breakdown = []
                total_all = 0
                correct_all = 0
                for row in rows:
                    total_all += row[2] or 0
                    correct_all += row[3] or 0
                    breakdown.append({
                        "source": row[0],
                        "direction": row[1],
                        "total": row[2] or 0,
                        "correct": row[3] or 0,
                        "accuracy_pct": round(((row[3] or 0) / max(row[2] or 0, 1)) * 100, 2),
                        "avg_return_pct": round(row[4] or 0, 2),
                    })

                return Result.ok({
                    "symbol": symbol,
                    "total": total_all,
                    "correct": correct_all,
                    "accuracy_pct": round((correct_all / max(total_all, 1)) * 100, 2),
                    "breakdown": breakdown,
                })
        except Exception as e:
            logger.error("Failed to get accuracy by symbol: %s", e)
            self._count_unavailable_read(reason="error")
            return Result.ok({"symbol": symbol, "total": 0, "accuracy_pct": 0, "breakdown": []})

    @staticmethod
    def _count_unavailable_read(reason: str = "no_database") -> None:
        """Count an unavailable accuracy read so it is never silent (audit S2)."""
        try:
            from apps.api.metrics import get_prometheus_exporter

            get_prometheus_exporter().inc(
                "accuracy_tracking_read_unavailable_total", labels={"reason": reason}
            )
        except Exception:  # noqa: BLE001 — metric plumbing must not break reads
            pass
