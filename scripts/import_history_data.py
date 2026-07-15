"""
Import historical data from JSON files in history_data/ into the quotes table.

Each JSON file is named after the Persian symbol with _history suffix (e.g., khodro_history.json)
and contains an array of daily OHLCV records (same format as backtest data).

Usage:
    python scripts/import_history_data.py
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

from core.database import close_database, get_session, init_database
from core.logging import get_logger
from models.instrument import InstrumentModel
from models.quote import QuoteModel

logger = get_logger(__name__)

HISTORY_DATA_DIR = Path("history_data")
BATCH_SIZE = 5000


def parse_json_record(record: dict, symbol: str, instrument_id: str) -> dict | None:
    """Map a JSON record from the history file to a QuoteModel-compatible dict."""
    date_str = record.get("date", "")
    time_str = record.get("time", "")
    tno = record.get("tno", 0) or 0
    tvol = record.get("tvol", 0) or 0
    tval = record.get("tval", 0) or 0
    pmin = record.get("pmin", 0) or 0
    pmax = record.get("pmax", 0) or 0
    py = record.get("py", 0) or 0
    pf = record.get("pf", 0) or 0
    pl = record.get("pl", 0) or 0
    plc = record.get("plc", 0) or 0
    plp = record.get("plp", 0) or 0
    pc = record.get("pc", 0) or 0

    # Skip zero-volume records (non-trading days)
    if tvol == 0 and tval == 0 and tno == 0 and pc == 0:
        return None

    quote_id = f"ht_{instrument_id}_{date_str}"

    return {
        "id": quote_id,
        "instrument_id": instrument_id,
        "symbol": symbol,
        "price_close": float(pc) if pc else None,
        "price_open": float(pf) if pf else None,
        "price_high": float(pmax) if pmax else None,
        "price_low": float(pmin) if pmin else None,
        "price_last": float(pl) if pl else None,
        "price_change": float(plc) if plc else None,
        "price_change_pct": float(plp) if plp else None,
        "volume": int(tvol) if tvol else None,
        "value": float(tval) if tval else None,
        "trade_count": int(tno) if tno else None,
        "price_yesterday": float(py) if py else None,
        "price_first": float(pf) if pf else None,
        "price_max": float(pmax) if pmax else None,
        "price_min": float(pmin) if pmin else None,
        "time": time_str or None,
        "date": date_str or None,
        "timeframe": "1d",
        "data_source": "history",
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
    """Import a single JSON file's records into the quotes table."""
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
        parsed = parse_json_record(record, symbol, instrument_id)
        if parsed is not None:
            records.append(parsed)

    if not records:
        return 0

    # Batch insert with upsert (ON CONFLICT DO NOTHING)
    total_inserted = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        try:
            stmt = pg_insert(QuoteModel).values(batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
            await session.execute(stmt)
            await session.flush()
            total_inserted += len(batch)
        except Exception as e:
            logger.warning("  [ERR] %s batch at %d: %s", repr(symbol), i, str(e)[:150])
            for rec in batch:
                try:
                    await session.execute(
                        pg_insert(QuoteModel).values(rec).on_conflict_do_nothing(index_elements=["id"])
                    )
                    await session.flush()
                    total_inserted += 1
                except Exception as e2:
                    logger.warning("  [SKIP] %s record %s: %s", repr(symbol), rec.get("date"), str(e2)[:100])

    logger.info("  [OK] %s: %d records (total %d in file)", repr(symbol), total_inserted, len(records))
    stats["total_records"] += total_inserted
    stats["total_files"] += 1
    return total_inserted


def extract_symbol_from_filename(filename: str) -> str:
    """Extract symbol from filename like 'khodro_history.json' -> 'khodro'."""
    name = filename
    # Remove _history suffix and .json extension
    if name.endswith("_history.json"):
        name = name[: -len("_history.json")]
    elif name.endswith(".json"):
        name = name[: -len(".json")]
    return name


async def main():
    print("=" * 60)
    print("  Import History Data -> quotes table")
    print("=" * 60)

    if not HISTORY_DATA_DIR.is_dir():
        logger.error("Directory not found: %s", HISTORY_DATA_DIR)
        return 1

    # Find all JSON files
    json_files = sorted(HISTORY_DATA_DIR.glob("*.json"))
    if not json_files:
        logger.error("No JSON files found in %s", HISTORY_DATA_DIR)
        return 1

    logger.info("Found %d JSON files in %s", len(json_files), HISTORY_DATA_DIR)

    await init_database()

    async for session in get_session():
        symbol_map = await build_symbol_map(session)

        # Pre-count existing history quotes
        cnt_before = await session.execute(
            select(func.count()).select_from(QuoteModel).where(QuoteModel.data_source == "history")
        )
        existing_before = cnt_before.scalar() or 0
        logger.info("Existing history quotes before import: %d", existing_before)

        missing_instruments = []

        stats = {
            "total_files": 0,
            "total_records": 0,
            "failed_files": 0,
        }

        start_time = time.time()

        for file_path in json_files:
            symbol = extract_symbol_from_filename(file_path.name)

            instrument_id = symbol_map.get(symbol)
            if instrument_id is None:
                missing_instruments.append(symbol)
                continue

            await import_file(session, file_path, symbol, instrument_id, stats)

            if stats["total_files"] % 100 == 0 and stats["total_files"] > 0:
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
            print("\n  Symbols not found in instruments table (first 20):")
            for sym in missing_instruments[:20]:
                print(f"    - {sym}")
            if len(missing_instruments) > 20:
                print(f"    ... and {len(missing_instruments) - 20} more")

        cnt_after = await session.execute(
            select(func.count()).select_from(QuoteModel).where(QuoteModel.data_source == "history")
        )
        existing_after = cnt_after.scalar() or 0
        print(f"\n  History quotes before:  {existing_before:,}")
        print(f"  History quotes after:   {existing_after:,}")
        print(f"  Net increase:           {existing_after - existing_before:,}")
        print("=" * 60)

        break

    await close_database()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
