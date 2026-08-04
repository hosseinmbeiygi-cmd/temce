#!/usr/bin/env python
"""Import transaction_all_symbols/ JSON files into brsapi_intraday_trades table."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import json

from sqlalchemy import text

from core.database import close_database, get_session, init_database

DATA_DIR = Path("transaction_all_symbols")


async def ensure_table():
    async for session in get_session():
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS brsapi_intraday_trades (
                id BIGSERIAL PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL,
                trade_date VARCHAR(20) NOT NULL,
                trade_time VARCHAR(20),
                volume DOUBLE PRECISION,
                price DOUBLE PRECISION,
                canceled INTEGER DEFAULT 0,
                row_number INTEGER,
                fetched_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_it_symbol ON brsapi_intraday_trades(symbol)"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_it_date ON brsapi_intraday_trades(trade_date)"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_it_symbol_date ON brsapi_intraday_trades(symbol, trade_date)"))
        await session.commit()
        break


async def import_all(dry_run=False):
    if not DATA_DIR.exists():
        print(f"Directory not found: {DATA_DIR}")
        return

    symbol_files = sorted(
        f for f in DATA_DIR.glob("*.json")
        if f.name not in ("progress.json", "daily_counter.json")
    )
    print(f"Found {len(symbol_files)} symbol files")

    total_rows = 0
    total_files = 0
    errors = 0

    for fp in symbol_files:
        symbol = fp.stem
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                continue

            rows = []
            for day in data:
                date_str = day.get("date", "")
                for txn in day.get("transactions", []):
                    rows.append({
                        "symbol": symbol,
                        "trade_date": date_str,
                        "trade_time": txn.get("time", ""),
                        "volume": txn.get("volume"),
                        "price": txn.get("price"),
                        "canceled": txn.get("canceled", 0),
                        "row_number": txn.get("row"),
                    })

            if dry_run:
                if rows:
                    print(f"  {symbol}: {len(rows)} trades ({len(data)} days)")
                total_rows += len(rows)
                total_files += 1
                continue

            if not rows:
                continue

            async for session in get_session():
                for r in rows:
                    await session.execute(text("""
                        INSERT INTO brsapi_intraday_trades
                            (symbol, trade_date, trade_time, volume, price, canceled, row_number)
                        VALUES (:symbol, :trade_date, :trade_time, :volume, :price, :canceled, :row_number)
                    """), r)
                await session.commit()
                break

            total_rows += len(rows)
            total_files += 1
            if total_files % 100 == 0:
                print(f"  Progress: {total_files} files, {total_rows} rows")

        except Exception as e:
            errors += 1
            print(f"  ERR {symbol}: {e}")

    print()
    print(f"Done: {total_files} files, {total_rows} rows, {errors} errors")


async def _run(dry_run):
    print("=" * 60)
    print("  Transaction All Symbols Import")
    print("=" * 60)
    if dry_run:
        print("  Mode: DRY RUN")
    print()

    if not dry_run:
        await init_database()
        await ensure_table()

    try:
        await import_all(dry_run)
    finally:
        if not dry_run:
            await close_database()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args.dry_run))
