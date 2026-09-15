"""Dry-run the rolling accuracy circuit breaker against historical data.

Walks the breaker across a series of historical dates, recomputing the
breaker verdict for each, and prints the timeline. This lets you see
*when* the breaker would have tripped over the recent history and how
much signal volume would have been lost.

Usage:
    DATABASE_URL=postgresql+... python scripts/dryrun_circuit_breaker.py
    DATABASE_URL=postgresql+... python scripts/dryrun_circuit_breaker.py --window 5
    DATABASE_URL=postgresql+... python scripts/dryrun_circuit_breaker.py --threshold 45
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def _daily_snapshot(
    engine, *, on_date: datetime, window: int, threshold: float, min_samples: int
) -> tuple[datetime, bool, float, int]:
    """Compute the breaker verdict as it would have looked on ``on_date``.

    Returns (date, tripped, accuracy_pct, sample_size).
    """
    cutoff = on_date - timedelta(days=window)
    query = text(
        """
        SELECT
          COUNT(*) AS n,
          AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END) AS acc
        FROM signal_accuracy
        WHERE timeframe = 'daily'
          AND outcome_set_at IS NOT NULL
          AND outcome_set_at >= :cutoff
          AND outcome_set_at < :on_date
        """
    )
    async with engine.connect() as conn:
        row = (await conn.execute(query, {"cutoff": cutoff, "on_date": on_date})).first()
    n = int(row[0] or 0)
    acc = float(row[1] or 0.0) * 100.0 if n else 0.0
    tripped = n >= min_samples and acc < threshold
    return on_date, tripped, acc, n


async def _run(args: argparse.Namespace) -> int:
    db = os.environ.get("DATABASE_URL")
    if not db:
        print("DATABASE_URL not set", file=sys.stderr)
        return 1

    engine = create_async_engine(db)
    try:
        # Find the date range present in the table.
        async with engine.connect() as conn:
            range_row = (
                await conn.execute(
                    text(
                        "SELECT MIN(outcome_set_at)::date, MAX(outcome_set_at)::date "
                        "FROM signal_accuracy WHERE outcome_set_at IS NOT NULL"
                    )
                )
            ).first()
        if not range_row or not range_row[0]:
            print("No outcome_set_at data in signal_accuracy", file=sys.stderr)
            return 1
        start_date, end_date = range_row[0], range_row[1]

        # Sample daily from start_date + window to end_date.
        dates: list[datetime] = []
        d = start_date + timedelta(days=args.window)
        while d <= end_date:
            dates.append(d)
            d += timedelta(days=1)

        print(
            f"\n=== Circuit-breaker dry-run (window={args.window}d, threshold={args.threshold}%, min_samples={args.min_samples}) ==="
        )
        print(f"  Date range in DB: {start_date} → {end_date}")
        print(f"  Snapshots computed: {len(dates)}\n")

        print(f"  {'date':12s} | tripped | acc%   | n")
        print(f"  {'-' * 11}-+-'{'-' * 7}'-+-'{'-' * 5}'-+-{'-' * 4}")
        tripped_count = 0
        total_n = 0
        weighted_acc = 0.0
        for snap in dates:
            res = await _daily_snapshot(
                engine,
                on_date=snap,
                window=args.window,
                threshold=args.threshold,
                min_samples=args.min_samples,
            )
            date, tripped, acc, n = res
            if tripped:
                tripped_count += 1
            total_n += n
            weighted_acc += acc * n
            marker = "YES" if tripped else "no"
            print(f"  {str(date):12s} |   {marker:3s}  | {acc:5.1f} | {n:4d}")
        avg_acc = (weighted_acc / total_n) if total_n else 0.0
        print(
            f"\n  Summary: {tripped_count}/{len(dates)} days tripped ({tripped_count / len(dates) * 100:.1f}%), "
            f"weighted avg accuracy = {avg_acc:.1f}%"
        )
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=50.0)
    parser.add_argument("--min-samples", type=int, default=20)
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
