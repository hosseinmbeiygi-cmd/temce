"""
Import real/legal trading data from JSON files in real_legal_history_json/ into
the brsapi_historical_real_legal table (HistoricalRealLegalModel).

Each JSON file is named after a Persian symbol (e.g., khodro.json) and contains
an array of daily records with fields:
  date, Buy_CountI, Buy_CountN, Sell_CountI, Sell_CountN,
  Buy_I_Volume, Buy_N_Volume, Sell_I_Volume, Sell_N_Volume,
  Buy_I_Value, Buy_N_Value, Sell_I_Value, Sell_N_Value

Where I = Institutional (Legal), N = Natural (Real person).

Usage:
    python scripts/import_real_legal.py
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
import contextlib
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

from brsapi.models.tsetmc import HistoricalRealLegalModel
from core.database import close_database, get_session, init_database
from core.logging import get_logger
from models.instrument import InstrumentModel

logger = get_logger(__name__)

REAL_LEGAL_DIR = Path("real_legal_history_json")
BATCH_SIZE = 500  # asyncpg has a parameter limit (~32767), keep batches small


def parse_record(record: dict, symbol: str, instrument_id: str) -> dict | None:
    """Map a JSON record to a HistoricalRealLegalModel-compatible dict."""
    date_str = record.get("date", "")
    if not date_str:
        return None

    # I = Institutional (Legal), N = Natural (Real person)
    buy_legal_count = record.get("Buy_CountI", 0) or 0
    buy_real_count = record.get("Buy_CountN", 0) or 0
    sell_legal_count = record.get("Sell_CountI", 0) or 0
    sell_real_count = record.get("Sell_CountN", 0) or 0
    buy_legal_volume = record.get("Buy_I_Volume", 0) or 0
    buy_real_volume = record.get("Buy_N_Volume", 0) or 0
    sell_legal_volume = record.get("Sell_I_Volume", 0) or 0
    sell_real_volume = record.get("Sell_N_Volume", 0) or 0
    buy_legal_value = record.get("Buy_I_Value", 0) or 0
    buy_real_value = record.get("Buy_N_Value", 0) or 0
    sell_legal_value = record.get("Sell_I_Value", 0) or 0
    sell_real_value = record.get("Sell_N_Value", 0) or 0

    return {
        "symbol": symbol,
        "date": date_str,
        "buy_legal_count": int(buy_legal_count) if buy_legal_count else None,
        "buy_real_count": int(buy_real_count) if buy_real_count else None,
        "sell_legal_count": int(sell_legal_count) if sell_legal_count else None,
        "sell_real_count": int(sell_real_count) if sell_real_count else None,
        "buy_legal_volume": int(buy_legal_volume) if buy_legal_volume else None,
        "buy_real_volume": int(buy_real_volume) if buy_real_volume else None,
        "sell_legal_volume": int(sell_legal_volume) if sell_legal_volume else None,
        "sell_real_volume": int(sell_real_volume) if sell_real_volume else None,
        "buy_legal_value": float(buy_legal_value) if buy_legal_value else None,
        "buy_real_value": float(buy_real_value) if buy_real_value else None,
        "sell_legal_value": float(sell_legal_value) if sell_legal_value else None,
        "sell_real_value": float(sell_real_value) if sell_real_value else None,
    }


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
    """Import a single JSON file's records into the real_legal table."""
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
    for record in raw:
        parsed = parse_record(record, symbol, instrument_id)
        if parsed is not None:
            records.append(parsed)

    if not records:
        logger.info("  [OK] %s: 0 records", repr(symbol))
        stats["total_files"] += 1
        return 0

    total_inserted = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        try:
            # Use raw INSERT with DEFAULT for auto-increment id
            from sqlalchemy import text as sa_text
            cols = list(batch[0].keys())
            cols_str = ', '.join(f'"{c}"' for c in cols)
            placeholders = ', '.join(f':{c}' for c in cols)
            stmt = sa_text(
                f'INSERT INTO "brsapi_historical_real_legal" ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
            )
            await session.execute(stmt, batch)
            await session.flush()
            total_inserted += len(batch)
        except Exception as e:
            logger.warning("  [ERR] %s batch at %d: %s", repr(symbol), i, str(e)[:150])
            with contextlib.suppress(Exception):
                await session.rollback()
                # Retry one by one
                from sqlalchemy import text as sa_text2
                for rec in batch:
                    cols = list(rec.keys())
                    cols_str = ', '.join(f'"{c}"' for c in cols)
                    placeholders = ', '.join(f':{c}' for c in cols)
                    try:
                        await session.execute(
                            sa_text2(f'INSERT INTO "brsapi_historical_real_legal" ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'),
                            rec
                        )
                        await session.flush()
                        total_inserted += 1
                    except Exception as e2:
                        logger.warning("  [SKIP] %s record: %s", repr(symbol), str(e2)[:100])

    logger.info("  [OK] %s: %d records", repr(symbol), total_inserted)
    stats["total_records"] += total_inserted
    stats["total_files"] += 1
    return total_inserted


async def main():
    print("=" * 60)
    print("  Import Real/Legal History -> brsapi_historical_real_legal table")
    print("=" * 60)

    if not REAL_LEGAL_DIR.is_dir():
        logger.error("Directory not found: %s", REAL_LEGAL_DIR)
        return 1

    json_files = sorted(REAL_LEGAL_DIR.glob("*.json"))
    if not json_files:
        logger.error("No JSON files found in %s", REAL_LEGAL_DIR)
        return 1

    logger.info("Found %d JSON files in %s", len(json_files), REAL_LEGAL_DIR)

    await init_database()

    async for session in get_session():
        symbol_map = await build_symbol_map(session)

        cnt_before = await session.execute(select(func.count()).select_from(HistoricalRealLegalModel))
        existing_before = cnt_before.scalar() or 0
        logger.info("Existing real_legal records before import: %d", existing_before)

        missing_instruments = []

        stats = {
            "total_files": 0,
            "total_records": 0,
            "failed_files": 0,
        }

        start_time = time.time()

        for file_path in json_files:
            symbol = file_path.stem

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

        cnt_after = await session.execute(select(func.count()).select_from(HistoricalRealLegalModel))
        existing_after = cnt_after.scalar() or 0
        print(f"\n  Real/legal records before: {existing_before:,}")
        print(f"  Real/legal records after:  {existing_after:,}")
        print(f"  Net increase:              {existing_after - existing_before:,}")
        print("=" * 60)

        break

    await close_database()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
