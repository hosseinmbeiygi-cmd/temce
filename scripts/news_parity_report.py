#!/usr/bin/env python
"""Read-only parity audit: ``news_articles`` (legacy) vs ``news_items`` (mirror).

Answers “are the two news schemas in sync right now?” over a recent window.
No writes: the SQL lives in :mod:`services.news_parity` and is SELECT-only.

Usage:
  python scripts/news_parity_report.py                # last 7 days, pretty
  python scripts/news_parity_report.py --days 30 --json
  python scripts/news_parity_report.py --days 2 --samples 20

Exit code: 0 = parity OK, 1 = divergence found, 2 = could not run (DB).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

sys.path.insert(0, ".")


async def _run(days: int, samples: int) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from core.config import settings
    from services.news_parity import news_parity_report

    url = settings.database_url_async or settings.database_url
    engine = create_async_engine(url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            return await news_parity_report(session, days=days, sample_limit=samples)
    finally:
        await engine.dispose()


def _print_pretty(report: dict[str, Any]) -> None:
    print("=" * 62)
    print("  NEWS PARITY — legacy news_articles vs news_items")
    print("=" * 62)
    print(f"  window:                last {report['window_days']} day(s)")
    print(f"  legacy total/recent:   {report['legacy_total']:,} / {report['legacy_recent']:,}")
    print(f"  mirror total/recent:   {report['mirror_total']:,} / {report['mirror_recent']:,}")
    print(f"  linked rows:           {report['linked_rows']:,}")
    print(f"  missing in mirror:     {report['legacy_missing_mirror']:,}")
    print(f"  missing in legacy:     {report['mirror_missing_legacy']:,}")
    print(f"  linked but no time:    {report['linked_missing_time']:,}")
    print(f"  parity ok:             {'YES' if report['parity_ok'] else 'NO'}")
    for row in report.get("sample_missing", []):
        print(f"    - {row['id']}: {row['title'][:70]}")
    print("-" * 62)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7, help="window in days (1..90)")
    ap.add_argument("--samples", type=int, default=10, help="missing-row samples (0..50)")
    ap.add_argument("--json", action="store_true", help="print raw JSON only")
    args = ap.parse_args(argv)

    try:
        report = asyncio.run(_run(args.days, args.samples))
    except Exception as exc:  # noqa: BLE001 — CLI: report and exit non-zero
        print(f"parity audit failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, default=str))
    else:
        _print_pretty(report)
    return 0 if report["parity_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
