#!/usr/bin/env python
"""
Import gold/currency history JSON files from gold_currency_history/ into the database.

Each JSON file contains OHLC data (open, high, low, close) with Persian dates.

Usage:
    python scripts/import_gold_currency_history.py                    # import all
    python scripts/import_gold_currency_history.py --symbol USD       # import one
    python scripts/import_gold_currency_history.py --dry-run          # preview only
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from sqlalchemy import text

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from core.database import close_database, get_session, init_database

DATA_DIR = Path("gold_currency_history")


def load_json(filepath: Path) -> list[dict]:
    """Load and validate a currency history JSON file."""
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [r for r in data if isinstance(r, dict) and r.get("date")]
    except Exception:
        return []


async def ensure_table() -> None:
    """Create brsapi_gold_coin_history table if it doesn't exist."""
    async for session in get_session():
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS brsapi_gold_coin_history (
                id BIGSERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                date VARCHAR(20) NOT NULL,
                price_open DOUBLE PRECISION,
                price_high DOUBLE PRECISION,
                price_low DOUBLE PRECISION,
                price_close DOUBLE PRECISION,
                fetched_at VARCHAR(30),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_gold_hist_symbol_date
            ON brsapi_gold_coin_history(symbol, date)
        """))
        await session.commit()
        break


async def import_all(symbol_filter: str | None = None, dry_run: bool = False) -> dict:
    """Import all gold/currency history files into the database."""
    stats = {"files": 0, "rows": 0, "symbols": 0, "errors": 0, "empty": 0}

    if not DATA_DIR.exists():
        print(f"Directory not found: {DATA_DIR}")
        return stats

    json_files = sorted(DATA_DIR.glob("*.json"))
    if symbol_filter:
        json_files = [f for f in json_files if f.stem == symbol_filter]

    for fp in json_files:
        symbol = fp.stem
        records = load_json(fp)
        stats["files"] += 1

        if not records:
            stats["empty"] += 1
            continue

        stats["symbols"] += 1

        if dry_run:
            print(f"  {symbol}: {len(records)} records ({records[0]['date']} -> {records[-1]['date']})")
            stats["rows"] += len(records)
            continue

        try:
            async for session in get_session():
                for rec in records:
                    await session.execute(text("""
                        INSERT INTO brsapi_gold_coin_history
                            (symbol, date, price_open, price_high, price_low, price_close)
                        VALUES
                            (:symbol, :date, :open, :high, :low, :close)
                        ON CONFLICT DO NOTHING
                    """), {
                        "symbol": symbol,
                        "date": rec["date"],
                        "open": rec.get("open"),
                        "high": rec.get("high"),
                        "low": rec.get("low"),
                        "close": rec.get("close"),
                    })
                await session.commit()
                break

            stats["rows"] += len(records)
            print(f"  {symbol}: {len(records)} records OK")

        except Exception as e:
            stats["errors"] += 1
            print(f"  {symbol}: ERROR - {e}")

    return stats


async def _run(symbol_filter: str | None, dry_run: bool):
    print("=" * 60)
    print("  Gold & Currency History Import")
    print("=" * 60)

    if dry_run:
        print("  Mode: DRY RUN (no data saved)")
    print(f"  Directory: {DATA_DIR.resolve()}")
    print()

    start = time.monotonic()

    if not dry_run:
        await init_database()
        await ensure_table()

    try:
        stats = await import_all(symbol_filter, dry_run)

        elapsed = time.monotonic() - start
        print()
        print("=" * 60)
        print(f"  Done in {elapsed:.1f}s")
        print(f"  Symbols:  {stats['symbols']}")
        print(f"  Files:    {stats['files']}")
        print(f"  Records:  {stats['rows']}")
        print(f"  Empty:    {stats['empty']}")
        print(f"  Errors:   {stats['errors']}")
        print("=" * 60)

    finally:
        if not dry_run:
            await close_database()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import gold/currency history")
    parser.add_argument("--symbol", help="Only import specific symbol (e.g. USD)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()
    asyncio.run(_run(args.symbol, args.dry_run))


if __name__ == "__main__":
    main()
