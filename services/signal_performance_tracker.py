"""Signal Performance Tracker — Feedback Loop for signal accuracy improvement.

Tracks the actual performance of generated signals over time and uses the
results to dynamically adjust indicator weights. This creates a self-learning
system that gets smarter over time.

Workflow:
  1. When a signal is generated, record entry price and timestamp
  2. After N days, check actual return vs predicted direction
  3. Update per-indicator accuracy scores
  4. Use accuracy scores to weight signals in future generation

Data sources:
  - signals table (generated signals with entry data)
  - brsapi_historical_daily (for actual price after signal)
  - signal_accuracy table (for cumulative accuracy tracking)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceResult:
    """Performance tracking result for a single signal."""
    signal_id: str
    symbol: str
    direction: str
    entry_price: float
    check_date: str
    actual_return_pct: float = 0.0
    was_correct: bool = False
    holding_period_days: int = 0


@dataclass
class AccuracySummary:
    """Accuracy summary for a specific indicator or source."""
    source: str
    total_signals: int = 0
    correct_signals: int = 0
    accuracy_pct: float = 0.0
    avg_return_pct: float = 0.0
    weight: float = 1.0


class SignalPerformanceTracker:
    """Tracks and evaluates signal performance over time."""

    def __init__(self, session: Any = None) -> None:
        self._session = session

    async def ensure_tables(self) -> None:
        """Create signal_performance and signal_accuracy tables if they don't exist."""
        if self._session is None:
            return

        from sqlalchemy import text

        await self._session.execute(text("""
            CREATE TABLE IF NOT EXISTS signal_performance (
                id SERIAL PRIMARY KEY,
                signal_id VARCHAR(64) NOT NULL,
                symbol VARCHAR(32) NOT NULL,
                direction VARCHAR(16) NOT NULL,
                entry_price NUMERIC NOT NULL,
                entry_date DATE NOT NULL,
                source VARCHAR(64) DEFAULT 'technical',
                check_3d_return NUMERIC,
                check_10d_return NUMERIC,
                was_correct_3d BOOLEAN,
                was_correct_10d BOOLEAN,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(signal_id)
            )
        """))

        await self._session.execute(text("""
            CREATE TABLE IF NOT EXISTS signal_accuracy (
                id SERIAL PRIMARY KEY,
                source VARCHAR(64) NOT NULL,
                period VARCHAR(16) NOT NULL,
                total_signals INT DEFAULT 0,
                correct_signals INT DEFAULT 0,
                avg_return NUMERIC DEFAULT 0,
                weight NUMERIC DEFAULT 1.0,
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(source, period)
            )
        """))

        await self._session.commit()

    async def record_signal(
        self,
        signal_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        source: str = "technical",
    ) -> None:
        """Record a new signal for tracking."""
        if self._session is None:
            return

        from sqlalchemy import text

        today = date.today()
        await self._session.execute(text("""
            INSERT INTO signal_performance (signal_id, symbol, direction, entry_price, entry_date, source)
            VALUES (:sid, :sym, :dir, :ep, :ed, :src)
            ON CONFLICT (signal_id) DO NOTHING
        """), {"sid": signal_id, "sym": symbol, "dir": direction, "ep": entry_price, "ed": today, "src": source})
        await self._session.commit()

    async def evaluate_pending_signals(self) -> list[PerformanceResult]:
        """Evaluate signals that are 3 or 10 days old."""
        if self._session is None:
            return []

        from sqlalchemy import text

        today = date.today()

        # Find signals that need 3-day check
        result_3d = await self._session.execute(text("""
            SELECT sp.id, sp.signal_id, sp.symbol, sp.direction, sp.entry_price,
                   sp.entry_date, sp.source
            FROM signal_performance sp
            WHERE sp.check_3d_return IS NULL
              AND sp.entry_date <= :check_date
        """), {"check_date": today - timedelta(days=3)})

        rows_3d = [dict(row._mapping) for row in result_3d.fetchall()]

        # Find signals that need 10-day check
        result_10d = await self._session.execute(text("""
            SELECT sp.id, sp.signal_id, sp.symbol, sp.direction, sp.entry_price,
                   sp.entry_date, sp.source
            FROM signal_performance sp
            WHERE sp.check_10d_return IS NULL
              AND sp.entry_date <= :check_date
        """), {"check_date": today - timedelta(days=10)})

        rows_10d = [dict(row._mapping) for row in result_10d.fetchall()]

        results: list[PerformanceResult] = []

        # Process 3-day checks
        for row in rows_3d:
            perf = await self._check_signal_performance(row, 3)
            if perf:
                results.append(perf)

        # Process 10-day checks
        for row in rows_10d:
            perf = await self._check_signal_performance(row, 10)
            if perf:
                results.append(perf)

        # Update accuracy summary
        await self._update_accuracy_summary()

        return results

    async def _check_signal_performance(self, row: dict[str, Any], days: int) -> PerformanceResult | None:
        """Check actual performance of a signal after N days."""
        from sqlalchemy import text

        symbol = row["symbol"]
        entry_price = float(row["entry_price"])
        direction = row["direction"]
        entry_date = row["entry_date"]
        _source = row.get("source", "technical")
        record_id = row["id"]

        if entry_price <= 0:
            return None

        # Fetch price after N days
        check_date = entry_date + timedelta(days=days)
        result = await self._session.execute(text("""
            SELECT price_close
            FROM brsapi_historical_daily
            WHERE symbol = :sym AND date >= :check_date
            ORDER BY date ASC
            LIMIT 1
        """), {"sym": symbol, "check_date": check_date})

        row_price = result.fetchone()
        if not row_price:
            return None

        exit_price = float(row_price[0])
        if exit_price <= 0:
            return None

        actual_return_pct = (exit_price - entry_price) / entry_price * 100

        # Determine if prediction was correct
        was_correct = False
        if direction == "buy" and actual_return_pct > 0 or direction == "sell" and actual_return_pct < 0:
            was_correct = True
        elif direction == "hold":
            was_correct = abs(actual_return_pct) < 2.0  # Hold is correct if price didn't move much

        # Update the record
        if days == 3:
            await self._session.execute(text("""
                UPDATE signal_performance
                SET check_3d_return = :ret, was_correct_3d = :correct
                WHERE id = :id
            """), {"ret": actual_return_pct, "correct": was_correct, "id": record_id})
        elif days == 10:
            await self._session.execute(text("""
                UPDATE signal_performance
                SET check_10d_return = :ret, was_correct_10d = :correct
                WHERE id = :id
            """), {"ret": actual_return_pct, "correct": was_correct, "id": record_id})

        await self._session.commit()

        return PerformanceResult(
            signal_id=row["signal_id"],
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            check_date=str(check_date),
            actual_return_pct=actual_return_pct,
            was_correct=was_correct,
            holding_period_days=days,
        )

    async def _update_accuracy_summary(self) -> None:
        """Update the signal_accuracy table with latest stats."""
        from sqlalchemy import text

        # Update 3-day accuracy per source
        await self._session.execute(text("""
            INSERT INTO signal_accuracy (source, period, total_signals, correct_signals, avg_return, weight, updated_at)
            SELECT source, '3d',
                   COUNT(*),
                   SUM(CASE WHEN was_correct_3d THEN 1 ELSE 0 END),
                   AVG(check_3d_return),
                   GREATEST(0.1, LEAST(3.0,
                       CAST(SUM(CASE WHEN was_correct_3d THEN 1 ELSE 0 END) AS FLOAT) /
                       GREATEST(COUNT(*), 1) * 2.0
                   )),
                   NOW()
            FROM signal_performance
            WHERE check_3d_return IS NOT NULL
            GROUP BY source
            ON CONFLICT (source, period) DO UPDATE SET
                total_signals = EXCLUDED.total_signals,
                correct_signals = EXCLUDED.correct_signals,
                avg_return = EXCLUDED.avg_return,
                weight = EXCLUDED.weight,
                updated_at = NOW()
        """))

        # Update 10-day accuracy per source
        await self._session.execute(text("""
            INSERT INTO signal_accuracy (source, period, total_signals, correct_signals, avg_return, weight, updated_at)
            SELECT source, '10d',
                   COUNT(*),
                   SUM(CASE WHEN was_correct_10d THEN 1 ELSE 0 END),
                   AVG(check_10d_return),
                   GREATEST(0.1, LEAST(3.0,
                       CAST(SUM(CASE WHEN was_correct_10d THEN 1 ELSE 0 END) AS FLOAT) /
                       GREATEST(COUNT(*), 1) * 2.0
                   )),
                   NOW()
            FROM signal_performance
            WHERE check_10d_return IS NOT NULL
            GROUP BY source
            ON CONFLICT (source, period) DO UPDATE SET
                total_signals = EXCLUDED.total_signals,
                correct_signals = EXCLUDED.correct_signals,
                avg_return = EXCLUDED.avg_return,
                weight = EXCLUDED.weight,
                updated_at = NOW()
        """))

        await self._session.commit()

    async def get_accuracy_by_source(self, period: str = "3d") -> list[AccuracySummary]:
        """Get accuracy summary for each signal source."""
        if self._session is None:
            return []

        from sqlalchemy import text

        result = await self._session.execute(text("""
            SELECT source, total_signals, correct_signals, avg_return, weight
            FROM signal_accuracy
            WHERE period = :period
            ORDER BY weight DESC
        """), {"period": period})

        return [
            AccuracySummary(
                source=row[0],
                total_signals=row[1],
                correct_signals=row[2],
                accuracy_pct=(row[2] / row[1] * 100) if row[1] > 0 else 0,
                avg_return_pct=float(row[3] or 0),
                weight=float(row[4] or 1.0),
            )
            for row in result.fetchall()
        ]

    async def get_weight_adjustments(self) -> dict[str, float]:
        """Get current weight adjustments based on historical accuracy."""
        summaries = await self.get_accuracy_by_source("3d")
        return {s.source: s.weight for s in summaries}
