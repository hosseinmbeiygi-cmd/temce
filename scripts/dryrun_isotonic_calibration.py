"""Train the per-market isotonic calibrators against the live DB.

This is the operator entry point: run it on a schedule (e.g. weekly)
and the resulting models are persisted to ``isotonic_calibration``
where the live apply path can read them.

Usage:
    DATABASE_URL=postgresql+... python scripts/dryrun_isotonic_calibration.py
    DATABASE_URL=postgresql+... python scripts/dryrun_isotonic_calibration.py --window 90
    DATABASE_URL=postgresql+... python scripts/dryrun_isotonic_calibration.py --min-samples 200
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

# Ensure the project root is on sys.path so ``import services.*`` works
# when this script is invoked directly (e.g. via ``python scripts/...``).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def _run(args: argparse.Namespace) -> int:
    db = os.environ.get("DATABASE_URL")
    if not db:
        print("DATABASE_URL not set", file=sys.stderr)
        return 1

    # Imported here to keep --help fast.
    from services.isotonic_calibrator import (
        SUPPORTED_MARKETS,
        train_all_markets,
    )

    engine = create_async_engine(db)
    try:
        results = await train_all_markets(engine, window_days=args.window)
    finally:
        await engine.dispose()

    print(f"\n=== Isotonic per-market calibration (window={args.window}d) ===\n")
    print(f"  {'market':12s} | {'status':10s} | n    | brier  | ece")
    print(f"  {'-' * 12}-+-{'-' * 10}-+-{'-' * 5}-+-{'-' * 6}-+-{'-' * 6}")

    trained = 0
    for market in SUPPORTED_MARKETS:
        model = results.get(market)
        if model is None:
            print(f"  {market:12s} | skipped   |")
            continue
        trained += 1
        print(f"  {market:12s} | ok        | {model.n_samples:4d} | {model.brier_score:.4f} | {model.ece:.4f}")

    print(f"\n  {trained} market(s) trained, persisted to isotonic_calibration table.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, default=180, help="days of history (default 180)")
    parser.add_argument("--min-samples", type=int, default=100)
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
