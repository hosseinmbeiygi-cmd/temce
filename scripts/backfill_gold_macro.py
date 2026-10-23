"""One-shot FRED backfill for the gold macro indicators.

Usage::

    python scripts/backfill_gold_macro.py                  # last 2 years
    python scripts/backfill_gold_macro.py --years 3
    python scripts/backfill_gold_macro.py --start 2024-01-01 --end 2024-12-31

It reads ``FRED_API_KEY`` from the repository ``.env`` (through
``core.config.Settings``), fetches every observation for DFII10 and
DTWEXBGS, upserts by ``(indicator, as_of)`` and prints count/min/max plus
percentiles for each stored series.  Re-running the same window is safe.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from providers.macro_sources.fred import (  # noqa: E402
    FRED_DXY_BROAD_SERIES,
    FRED_TIPS_10Y_SERIES,
    FREDClient,
)
from services.gold.macro_sync import (  # noqa: E402
    MacroSyncService,
    summarize_indicator_values,
)

SERIES_CHOICES = (FRED_TIPS_10Y_SERIES, FRED_DXY_BROAD_SERIES)


def _default_start(years: int) -> str:
    return (datetime.now(UTC).date() - timedelta(days=365 * years)).isoformat()


async def _indicator_stats(session, series_id: str) -> dict:
    from sqlalchemy import select

    from models.gold_macro import GoldMacroIndicatorModel

    statement = select(GoldMacroIndicatorModel.value).where(
        GoldMacroIndicatorModel.indicator == f"FRED_{series_id}"
    )
    values = (await session.execute(statement)).scalars().all()
    return summarize_indicator_values(values)


async def run(args: argparse.Namespace) -> int:
    from core.database import get_session, init_database

    observation_start = args.start or _default_start(args.years)
    await init_database()

    async for session in get_session():
        service = MacroSyncService(session, fred_provider=FREDClient())
        result = await service.backfill_fred_indicators(
            observation_start=observation_start,
            observation_end=args.end,
            indicators=tuple(args.series),
        )

        stats = {
            series_id: await _indicator_stats(session, series_id)
            for series_id in args.series
        }
        payload = {
            "observation_start": observation_start,
            "observation_end": args.end,
            "sync": asdict(result),
            "stored": stats,
            # A quick, explicit view of the percentile thresholds the live
            # posture uses for the broad dollar index.
            "dxy_percentile_thresholds": {
                "p20": stats.get(FRED_DXY_BROAD_SERIES, {}).get("p20"),
                "p80": stats.get(FRED_DXY_BROAD_SERIES, {}).get("p80"),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0 if result.ok else 1

    print(json.dumps({"error": "could not obtain a database session"}))
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        type=int,
        default=2,
        help="Backfill window in years when --start is omitted (default: 2).",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Explicit observation_start (ISO date); overrides --years.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Optional observation_end (ISO date).",
    )
    parser.add_argument(
        "--series",
        nargs="+",
        choices=SERIES_CHOICES,
        default=list(SERIES_CHOICES),
        help="FRED series to backfill (default: both).",
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
