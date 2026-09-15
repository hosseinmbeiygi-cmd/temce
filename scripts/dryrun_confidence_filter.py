"""Dry-run the daily confidence-floor filter against historical outcomes.

Estimates the user-facing accuracy lift if ``SIGNAL_PIPELINE_MIN_CONFIDENCE``
were set to a given threshold. Uses the same DB rows the live pipeline
sees, so the numbers are directly comparable to production.

Usage:
    DATABASE_URL=postgresql+... python scripts/dryrun_confidence_filter.py
    DATABASE_URL=postgresql+... python scripts/dryrun_confidence_filter.py --threshold 0.50
    DATABASE_URL=postgresql+... python scripts/dryrun_confidence_filter.py --sweep 0.30,0.40,0.45,0.50,0.55
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@dataclass(frozen=True)
class Bucket:
    threshold: float
    n: int
    accuracy_pct: float
    coverage_pct: float


async def _compute(engine, threshold: float, timeframe: str) -> Bucket:
    """Run a single threshold against the DB and return metrics."""
    async with engine.connect() as c:
        n_row = (
            await c.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM signal_accuracy
                    WHERE timeframe = :tf AND signal_confidence >= :thr
                    """
                ),
                {"tf": timeframe, "thr": threshold},
            )
        ).first()
        n = int(n_row[0] or 0)

        a_row = (
            await c.execute(
                text(
                    """
                    SELECT AVG(CASE WHEN direction_correct THEN 1.0 ELSE 0.0 END)
                    FROM signal_accuracy
                    WHERE timeframe = :tf
                      AND signal_confidence >= :thr
                      AND direction_correct IS NOT NULL
                    """
                ),
                {"tf": timeframe, "thr": threshold},
            )
        ).scalar()
        acc = float(a_row or 0.0) * 100.0

        cov_row = (
            await c.execute(
                text(
                    """
                    SELECT
                      SUM(CASE WHEN signal_confidence >= :thr THEN 1 ELSE 0 END)::float
                      / NULLIF(COUNT(*), 0) * 100
                    FROM signal_accuracy
                    WHERE timeframe = :tf
                      AND direction_correct IS NOT NULL
                    """
                ),
                {"tf": timeframe, "thr": threshold},
            )
        ).scalar()
        cov = float(cov_row or 0.0)

    return Bucket(threshold=threshold, n=n, accuracy_pct=acc, coverage_pct=cov)


async def _run(args: argparse.Namespace) -> int:
    db = os.environ.get("DATABASE_URL")
    if not db:
        print("DATABASE_URL not set", file=sys.stderr)
        return 1

    engine = create_async_engine(db)
    try:
        if args.threshold is not None:
            thresholds = [args.threshold]
        else:
            thresholds = [float(x) for x in args.sweep.split(",") if x.strip()]

        # Single connection for the whole sweep.
        async with engine.connect() as c:
            # Baseline = threshold 0.0.
            base = await _compute(engine, 0.0, args.timeframe)
            buckets = [await _compute(engine, t, args.timeframe) for t in thresholds]

        print(f"\n=== Confidence-floor dry-run ({args.timeframe}, baseline n={base.n}) ===\n")
        print("  threshold |   n   | accuracy | coverage |  lift_vs_baseline")
        print("  --------- | ----- | -------- | -------- | -----------------")
        print(f"  {0.0:8.2f}  | {base.n:5d} | {base.accuracy_pct:6.1f}%  |  100.0%   |  (baseline)")

        for b in buckets:
            lift = b.accuracy_pct - base.accuracy_pct
            marker = "  <-- DEFAULT" if abs(b.threshold - 0.45) < 1e-6 else ""
            print(
                f"  {b.threshold:8.2f}  | {b.n:5d} | {b.accuracy_pct:6.1f}%  | {b.coverage_pct:6.1f}%   | {lift:+6.1f}%{marker}"
            )

        print(
            "\nInterpretation: a threshold that lifts accuracy by +15pp while keeping"
            "\n>= 30% coverage is the safe default. Anything below that means we throw"
            "\nout too many good signals; anything above and we lose too much volume."
        )
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", default="daily")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument(
        "--sweep",
        default="0.30,0.35,0.40,0.42,0.45,0.50,0.55,0.60",
    )
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
