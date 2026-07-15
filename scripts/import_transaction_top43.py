"""
Import transaction data from JSON files in transaction_top43/ into the
brsapi_intraday_trades table (IntradayTradeModel).

Each JSON file is named after the Persian symbol (e.g., اهرم.json) and contains
an array of day objects: {date, count, transactions: [{row, time, volume, price, canceled}]}

Usage:
    python scripts/import_transaction_top43.py
"""

from __future__ import annotations

# --- auto PYTHONPATH ---
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import json
import sys
import time
from pathlib import Path

# Force UTF-8 for console output on Windows
if sys.platform == "win32":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from brsapi.models.tsetmc import IntradayTradeModel
from core.database import close_database, get_session, init_database
from core.logging import get_logger
from models.instrument import InstrumentModel

logger = get_logger(__name__)

TRANSACTION_DIR = Path("transaction_top43")
BATCH_SIZE = 1000  # Keep batches manageable for large files

# Files to skip (not symbol data)
SKIP_FILES = {"daily_counter.json", "progress.json"}


async def build_symbol_map(session) -> dict[str, str]:
    """Build a mapping from symbol -> instrument_id from the instruments table."""
    stmt = select(InstrumentModel.symbol, InstrumentModel.id)
    result = await session.execute(stmt)
    rows = result.fetchall()
    symbol_map = {row[0]: row[1] for row in rows}
    logger.info("Loaded %d instruments from database", len(symbol_map))
    return symbol_map


async def import_file(
    session,
    file_path: Path,
    symbol: str,
    instrument_id: str,
    stats: dict,
) -> int:
    """Import a single JSON file's transaction records into the intraday trades table."""
    try:
        raw = json.loads(file_path.read_text("utf-8"))
    except Exception as e:
        logger.warning("  [SKIP] %s: could not parse JSON: %s", repr(symbol), e)
        stats["failed_files"] += 1
        return 0

    if not isinstance(raw, list):
        logger.warning("  [SKIP] %s: JSON is not a list", repr(symbol))
        stats["failed_files"] += 1
        return 0

    records = []
    skipped_dates = 0

    for day_entry in raw:
        trade_date = day_entry.get("date", "")
        transactions = day_entry.get("transactions", [])

        if not isinstance(transactions, list) or not transactions:
            skipped_dates += 1
            continue

        for tx in transactions:
            records.append({
                "symbol": symbol,
                "instrument_id": instrument_id,
                "row": tx.get("row"),
                "time": tx.get("time"),
                "volume": tx.get("volume"),
                "price": float(tx["price"]) if tx.get("price") else None,
                "canceled": bool(tx.get("canceled", 0)),
                "trade_date": trade_date,
            })

    if not records:
        logger.info("  [OK] %s: 0 records (no transactions)", repr(symbol))
        stats["total_files"] += 1
        return 0

    total_inserted = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        try:
            stmt = pg_insert(IntradayTradeModel).values(batch)
            stmt = stmt.on_conflict_do_nothing()  # auto-increment id, no unique conflict needed
            await session.execute(stmt)
            await session.flush()
            total_inserted += len(batch)
        except Exception as e:
            logger.warning("  [ERR] %s batch at %d: %s", repr(symbol), i, str(e)[:150])
            for rec in batch:
                try:
                    await session.execute(
                        pg_insert(IntradayTradeModel).values(rec).on_conflict_do_nothing()
                    )
                    await session.flush()
                    total_inserted += 1
                except Exception as e2:
                    logger.warning("  [SKIP] %s record: %s", repr(symbol), str(e2)[:100])

    logger.info(
        "  [OK] %s: %d records (%d days, %d skipped empty days)",
        repr(symbol),
        total_inserted,
        len(raw),
        skipped_dates,
    )
    stats["total_records"] += total_inserted
    stats["total_files"] += 1
    return total_inserted


async def main():
    print("=" * 60)
    print("  Import Transaction Top43 -> brsapi_intraday_trades table")
    print("=" * 60)

    if not TRANSACTION_DIR.is_dir():
        logger.error("Directory not found: %s", TRANSACTION_DIR)
        return 1

    # Find all JSON files (skip control files)
    json_files = sorted(
        f for f in TRANSACTION_DIR.glob("*.json")
        if f.name not in SKIP_FILES
    )

    if not json_files:
        logger.error("No JSON files found in %s", TRANSACTION_DIR)
        return 1

    logger.info("Found %d JSON files in %s", len(json_files), TRANSACTION_DIR)

    await init_database()

    async for session in get_session():
        symbol_map = await build_symbol_map(session)

        # Pre-count existing intraday trades
        cnt_before = await session.execute(select(func.count()).select_from(IntradayTradeModel))
        existing_before = cnt_before.scalar() or 0
        logger.info("Existing intraday trades before import: %d", existing_before)

        missing_instruments = []

        stats = {
            "total_files": 0,
            "total_records": 0,
            "failed_files": 0,
        }

        start_time = time.time()

        for file_path in json_files:
            symbol = file_path.stem  # filename without .json

            instrument_id = symbol_map.get(symbol)
            if instrument_id is None:
                missing_instruments.append(symbol)
                continue

            await import_file(session, file_path, symbol, instrument_id, stats)

            if stats["total_files"] % 5 == 0 and stats["total_files"] > 0:
                await session.commit()
                elapsed = time.time() - start_time
                logger.info(
                    "Progress: %d/%d files, %d records, %.1f sec",
                    stats["total_files"],
                    len(json_files),
                    stats["total_records"],
                    elapsed,
                )

        await session.commit()
        elapsed = time.time() - start_time

        print("\n" + "=" * 60)
        print("  Import Summary")
        print("=" * 60)
        print(f"  Total JSON files:      {len(json_files)}")
        print(f"  Successfully imported: {stats['total_files']} files")
        print(f"  Total records:         {stats['total_records']:,}")
        print(f"  Failed files:          {stats['failed_files']}")
        print(f"  Missing instruments:   {len(missing_instruments)}")
        print(f"  Time elapsed:          {elapsed:.1f} sec")

        if missing_instruments:
            print("\n  Symbols not found in instruments table:")
            for sym in missing_instruments:
                print(f"    - {sym}")

        cnt_after = await session.execute(select(func.count()).select_from(IntradayTradeModel))
        existing_after = cnt_after.scalar() or 0
        print(f"\n  Intraday trades before: {existing_before:,}")
        print(f"  Intraday trades after:  {existing_after:,}")
        print(f"  Net increase:           {existing_after - existing_before:,}")
        print("=" * 60)

        break

    await close_database()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
