"""
Backfill ins_id and instrument_id for all BrsApi tables.

This script updates existing records that are missing ins_id/instrument_id
by matching against brsapi_symbol_snapshots and the instruments table.

No API calls are made - it's a pure SQL backfill.
"""

# --- auto PYTHONPATH ---
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import sys
from pathlib import Path

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings

TABLES_WITH_SYMBOL = [
    "brsapi_historical_daily",
    "brsapi_historical_real_legal",
    "brsapi_intraday_trades",
    "brsapi_nav_records",
    "brsapi_shareholder_records",
    "brsapi_candlesticks",
    "brsapi_codal_announcements",
]


async def main():
    db_url = settings.database_url
    # Convert sync URL to async if needed
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print("Connecting to database...")
    engine = create_async_engine(db_url)

    async with engine.connect() as conn:
        for table in TABLES_WITH_SYMBOL:
            # Check if table exists
            r = await conn.execute(
                text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"),
                {"t": table},
            )
            if not r.fetchone():
                print(f"  [SKIP] {table} - table does not exist")
                continue

            # Check if symbol column exists
            r = await conn.execute(
                text("SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = :t AND column_name = 'symbol'"),
                {"t": table},
            )
            if not r.fetchone():
                print(f"  [SKIP] {table} - no symbol column")
                continue

            # 1. Backfill ins_id from snapshots
            r = await conn.execute(text(f"""
                UPDATE {table} AS t
                SET ins_id = s.ins_id
                FROM brsapi_symbol_snapshots AS s
                WHERE t.symbol = s.symbol
                  AND t.ins_id IS NULL
            """))
            rows_updated = r.rowcount

            # 2. Backfill ins_id from details (fallback)
            r = await conn.execute(text(f"""
                UPDATE {table} AS t
                SET ins_id = d.ins_id
                FROM brsapi_symbol_details AS d
                WHERE t.symbol = d.symbol
                  AND t.ins_id IS NULL
            """))
            rows_updated2 = r.rowcount

            # 3. Backfill instrument_id from instruments table
            r = await conn.execute(text(f"""
                UPDATE {table} AS t
                SET instrument_id = i.id
                FROM instruments AS i
                WHERE t.symbol = i.symbol
                  AND t.instrument_id IS NULL
            """))
            rows_updated3 = r.rowcount

            # 4. Remaining rows without ins_id
            r = await conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE ins_id IS NULL"))
            remaining = r.scalar()

            total_r = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            total = total_r.scalar()

            print(f"  [OK] {table}: {total} total, {rows_updated}+{rows_updated2} ins_id, {rows_updated3} instrument_id, {remaining} still missing ins_id")

        # Now check overall stats
        print()
        print("=== FINAL STATS ===")
        for table in TABLES_WITH_SYMBOL:
            r = await conn.execute(
                text(f"""SELECT COUNT(*), COUNT(*) FILTER (WHERE ins_id IS NOT NULL),
                    COUNT(*) FILTER (WHERE instrument_id IS NOT NULL)
                    FROM {table}"""),
            )
            total, has_ins, has_instr = r.fetchone()
            print(f"  {table}: {total} rows, {has_ins} with ins_id, {has_instr} with instrument_id")

    await engine.dispose()
    print()
    print("Backfill complete!")


if __name__ == "__main__":
    asyncio.run(main())
