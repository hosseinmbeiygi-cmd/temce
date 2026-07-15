"""
Merge year-partitioned historical tables into the main tables.
Also deduplicates brsapi_symbol_snapshots.
"""

# --- auto PYTHONPATH ---
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
# --- end auto PYTHONPATH ---

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from core.database import init_database


async def main():
    print("Initializing database connection...")
    await init_database()
    from core.database import engine

    async with engine.begin() as conn:
        # ── Step 1: Merge year tables ──
        result = await conn.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND (
                table_name LIKE 'brsapi_historical_daily_%'
                OR table_name LIKE 'brsapi_historical_real_legal_%'
            ) ORDER BY table_name
        """))
        year_tables = [row[0] for row in result.fetchall()]
        print(f"Found {len(year_tables)} year-partitioned tables")

        daily_tables = sorted([t for t in year_tables if t.startswith("brsapi_historical_daily_")])
        legal_tables = sorted([t for t in year_tables if t.startswith("brsapi_historical_real_legal_")])

        for main_table, tables in [("brsapi_historical_daily", daily_tables), ("brsapi_historical_real_legal", legal_tables)]:
            if not tables:
                continue
            print(f"\n--- {main_table} ---")

            # Get max id from main table to generate new unique ids
            result = await conn.execute(text(f'SELECT COALESCE(MAX(id), 0) FROM "{main_table}"'))
            max_id = result.scalar()

            for yt in tables:
                result = await conn.execute(text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :name ORDER BY ordinal_position
                """), {"name": yt})
                year_cols = [row[0] for row in result.fetchall()]

                # All columns except id (we generate new ids)
                data_cols = [c for c in year_cols if c != "id"]
                cols_str = ", ".join([f'"{c}"' for c in data_cols])

                result = await conn.execute(text(f'SELECT COUNT(*) FROM "{yt}"'))
                cnt = result.scalar()
                if cnt == 0:
                    await conn.execute(text(f'DROP TABLE IF EXISTS "{yt}"'))
                    print(f"  {yt}: empty, dropped")
                    continue

                # Use row_number() to generate unique ids
                await conn.execute(text(f"""
                    INSERT INTO "{main_table}" ("id", {cols_str})
                    SELECT ROW_NUMBER() OVER () + :start_id, {cols_str} FROM "{yt}"
                """), {"start_id": max_id})

                # Update max_id for next batch
                max_id += cnt

                await conn.execute(text(f'DROP TABLE IF EXISTS "{yt}"'))
                print(f"  {yt}: {cnt} rows merged & dropped")

        # ── Step 2: Deduplicate brsapi_symbol_snapshots ──
        print("\n--- Deduplicating brsapi_symbol_snapshots ---")
        result = await conn.execute(text('SELECT COUNT(*) FROM "brsapi_symbol_snapshots"'))
        before = result.scalar()
        print(f"  Before: {before} rows")

        await conn.execute(text("""
            DELETE FROM "brsapi_symbol_snapshots"
            WHERE id NOT IN (
                SELECT MAX(id) FROM "brsapi_symbol_snapshots"
                GROUP BY symbol
            )
        """))
        result = await conn.execute(text('SELECT COUNT(*) FROM "brsapi_symbol_snapshots"'))
        after = result.scalar()
        print(f"  After: {after} rows (removed {before - after} duplicates)")

        # ── Step 3: Deduplicate brsapi_historical_daily (symbol+date) ──
        print("\n--- Deduplicating brsapi_historical_daily ---")
        result = await conn.execute(text('SELECT COUNT(*) FROM "brsapi_historical_daily"'))
        before = result.scalar()
        print(f"  Before: {before} rows")

        await conn.execute(text("""
            DELETE FROM "brsapi_historical_daily"
            WHERE id NOT IN (
                SELECT MAX(id) FROM "brsapi_historical_daily"
                GROUP BY symbol, date
            )
        """))
        result = await conn.execute(text('SELECT COUNT(*) FROM "brsapi_historical_daily"'))
        after = result.scalar()
        print(f"  After: {after} rows (removed {before - after} duplicates)")

        # ── Step 4: Show final state ──
        print("\n=== Final table counts ===")
        result = await conn.execute(text("""
            SELECT t.table_name,
                   (xpath('/row/cnt/text()', query_to_xml(
                       format('SELECT COUNT(*) AS cnt FROM %I', t.table_name), false, true, ''
                   )))[1]::text::bigint AS row_count
            FROM information_schema.tables t
            WHERE t.table_schema = 'public'
            ORDER BY t.table_name
        """))
        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
