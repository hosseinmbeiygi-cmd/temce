#!/usr/bin/env python
"""
Import History Data from JSON Files to PostgreSQL

Reads all *_history.json files from the history_data/ directory and imports
them into the PostgreSQL quotes table using the QuoteModel.

Usage:
    python scripts/import_history_to_db.py
    python scripts/import_history_to_db.py --limit 10    # Only process first 10 files
    python scripts/import_history_to_db.py --skip-existing  # Skip symbols already in DB
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
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import close_database, get_session, init_database
from core.ids import new_id
from core.logging import get_logger, setup_logging
from models.instrument import InstrumentModel
from models.quote import QuoteModel

logger = get_logger(__name__)

HISTORY_DIR = _PROJECT_ROOT / "history_data"
DRY_RUN = False  # Set to True to just print what would be imported
BATCH_SIZE = 2000  # Commit every N records


def parse_args() -> dict:
    """Simple argument parser."""
    args = {
        "limit": None,
        "skip_existing": True,
        "symbol_filter": None,
    }
    for i, a in enumerate(sys.argv[1:]):
        if a == "--limit" and i + 2 < len(sys.argv):
            args["limit"] = int(sys.argv[i + 2])
        elif a == "--no-skip":
            args["skip_existing"] = False
        elif a == "--dry-run":
            global DRY_RUN
            DRY_RUN = True
        elif a == "--symbol":
            if i + 2 < len(sys.argv):
                args["symbol_filter"] = sys.argv[i + 2]
        elif a == "--help":
            print(__doc__)
            sys.exit(0)
    return args


async def get_instrument_map(session: AsyncSession) -> dict[str, str]:
    """Build a mapping of symbol -> instrument_id from the database."""
    result = await session.execute(
        select(InstrumentModel.id, InstrumentModel.symbol)
        .where(InstrumentModel.symbol.isnot(None))
        .where(InstrumentModel.status == "active")
    )
    mapping: dict[str, str] = {}
    for row in result.all():
        symbol = str(row.symbol).strip()
        inst_id = str(row.id)
        mapping[symbol] = inst_id
    return mapping


async def get_all_existing_dates(session: AsyncSession) -> dict[str, set[str]]:
    """Get all (instrument_id, date) pairs in a single query."""
    result = await session.execute(
        select(QuoteModel.instrument_id, QuoteModel.date).where(
            QuoteModel.timeframe == "1d",
        )
    )
    existing: dict[str, set[str]] = {}
    for inst_id, date in result.all():
        if inst_id and date:
            existing.setdefault(str(inst_id), set()).add(str(date))
    return existing


async def import_symbol_file(
    session: AsyncSession,
    json_path: Path,
    symbol: str,
    instrument_id: str,
    existing_dates: set[str],
    stats: dict,
) -> int:
    """Import a single symbol's history file into the quotes table."""
    try:
        with open(json_path, encoding="utf-8") as f:
            records = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("  ❌ Failed to read %s: %s", json_path.name, e)
        stats["failed_files"] += 1
        return 0

    if not isinstance(records, list):
        logger.error("  ❌ %s: expected array, got %s", json_path.name, type(records).__name__)
        stats["failed_files"] += 1
        return 0

    # Filter out zero-data records (where all price fields are 0)
    valid_records = [
        r for r in records
        if r.get("pl") or r.get("pc") or r.get("tvol", 0) > 0
    ]

    if not valid_records:
        logger.warning("  ⚠️  %s: no valid records (all zero)", json_path.name)
        stats["skipped_files"] += 1
        return 0

    imported = 0
    skipped = 0
    for record in valid_records:
        date_str = str(record.get("date", ""))
        time_str = str(record.get("time", ""))

        # Skip if date already exists for this instrument
        if date_str in existing_dates and date_str:
            skipped += 1
            continue

        if DRY_RUN:
            imported += 1
            continue

        quote = QuoteModel(
            id=new_id("quote"),
            instrument_id=instrument_id,
            symbol=symbol,
            price_last=float(record.get("pl", 0) or 0),
            price_close=float(record.get("pc", 0) or 0),
            price_open=float(record.get("pf", 0) or 0),  # pf = price first
            price_high=float(record.get("pmax", 0) or 0),
            price_low=float(record.get("pmin", 0) or 0),
            price_change=float(record.get("plc", 0) or 0),
            price_change_pct=float(record.get("plp", 0) or 0),
            price_yesterday=float(record.get("py", 0) or 0),
            price_first=float(record.get("pf", 0) or 0),
            price_max=float(record.get("pmax", 0) or 0),
            price_min=float(record.get("pmin", 0) or 0),
            volume=int(record.get("tvol", 0) or 0),
            value=float(record.get("tval", 0) or 0),
            trade_count=int(record.get("tno", 0) or 0),
            date=date_str,
            time=time_str,
            timeframe="1d",
            data_source="brsapi",
        )
        session.add(quote)
        imported += 1

    stats["imported"] += imported
    stats["skipped"] += skipped
    return imported


async def main() -> None:
    setup_logging()
    args = parse_args()
    symbol_filter = args["symbol_filter"]
    limit = args["limit"]
    skip_existing = args["skip_existing"]

    # Find all history JSON files
    if not HISTORY_DIR.exists():
        logger.error("❌ Directory not found: %s", HISTORY_DIR)
        sys.exit(1)

    json_files = sorted(HISTORY_DIR.glob("*_history.json"))
    if not json_files:
        logger.error("❌ No *_history.json files found in %s", HISTORY_DIR)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("  📥 Import History Data to PostgreSQL")
    logger.info("=" * 60)
    logger.info("  Directory:  %s", HISTORY_DIR)
    logger.info("  Files:      %d total", len(json_files))
    if limit:
        logger.info("  Limit:      %d files", limit)
    if symbol_filter:
        logger.info("  Symbol:     %s", symbol_filter)
    if skip_existing:
        logger.info("  Skip existing dates: YES")
    if DRY_RUN:
        logger.info("  🔶 DRY RUN — no data will be written")
    logger.info("")

    # Filter by symbol if specified
    if symbol_filter:
        json_files = [f for f in json_files if f.stem.startswith(symbol_filter)]
        logger.info("  Filtered to: %d files matching '%s'", len(json_files), symbol_filter)

    if limit:
        json_files = json_files[:limit]

    # Initialize database
    logger.info("Starting import: %d files to process", len(json_files))
    await init_database()

    stats = {
        "imported": 0,
        "skipped": 0,
        "skipped_files": 0,
        "failed_files": 0,
        "not_found": 0,
    }
    missing_symbols: list[str] = []

    async for session in get_session():
        # Build instrument map (symbol -> id)
        logger.info("🔍 Building instrument map...")
        instrument_map = await get_instrument_map(session)
        logger.info("  → %d instruments found in DB", len(instrument_map))

        # Get all existing dates in one batch query
        existing_by_instrument: dict[str, set[str]] = {}
        if skip_existing:
            logger.info("🔍 Loading existing dates from DB...")
            existing_by_instrument = await get_all_existing_dates(session)
            logger.info("  → %d instruments have existing data", len(existing_by_instrument))

        # Process each file
        # Log progress every 50 files
        max(1, len(json_files) // 30)

        for idx, json_path in enumerate(json_files, 1):
            symbol = json_path.stem.replace("_history", "").strip()
            instrument_id = instrument_map.get(symbol)

            if not instrument_id:
                logger.debug("  ⚠️  [%d/%d] %s: instrument not found in DB — skipping", idx, len(json_files), symbol)
                stats["not_found"] += 1
                missing_symbols.append(symbol)
                continue

            existing_dates = existing_by_instrument.get(instrument_id, set())

            # Import data
            count = await import_symbol_file(
                session, json_path, symbol, instrument_id, existing_dates, stats
            )

            symbol_label = f"{symbol[:12]:>12}" if len(symbol) <= 12 else symbol
            if count > 0:
                logger.info(
                    "  ✅ [%d/%d] %s: %d records imported",
                    idx, len(json_files), symbol_label, count,
                )
            else:
                logger.info(
                    "  ➖ [%d/%d] %s: no new records (skipped=%d)",
                    idx, len(json_files), symbol_label, stats["skipped"],
                )

            # Commit in batches (every BATCH_SIZE records)
            if stats["imported"] > 0 and stats["imported"] % BATCH_SIZE == 0 and not DRY_RUN:
                await session.commit()
                logger.info("  📦 Committed batch (%d records so far)", stats["imported"])

        # Final commit
        if not DRY_RUN:
            await session.commit()
        else:
            await session.rollback()

    await close_database()

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("  ✅ Import Complete!")
    logger.info("  📊 Summary:")
    logger.info("     Imported:     %d records", stats["imported"])
    logger.info("     Skipped:      %d records (already exist)", stats["skipped"])
    logger.info("     Not found:    %d symbols (not in instruments table)", stats["not_found"])
    if missing_symbols:
        logger.info("  First 20 missing symbols: %s", ", ".join(missing_symbols[:20]))
        if len(missing_symbols) > 20:
            logger.info("  ... and %d more", len(missing_symbols) - 20)
    logger.info("     Failed files: %d", stats["failed_files"])
    if DRY_RUN:
        logger.info("  🔶 DRY RUN — no data was written to database")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
