#!/usr/bin/env python
"""Check and fix autoincrement for brsapi_historical_daily partitioned table."""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import text

from core.config import settings


async def main():
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        # Step 1: Check parent table id column
        print("=== Step 1: Parent table column definition ===")
        r = await conn.execute(text("""
            SELECT column_name, column_default, is_identity, identity_generation
            FROM information_schema.columns
            WHERE table_name = 'brsapi_historical_daily'
              AND column_name = 'id'
        """))
        row = r.fetchone()
        if row:
            print(f"  default:    {row[1]}")
            print(f"  is_identity: {row[2]}")
            print(f"  gen:        {row[3]}")
        else:
            print("  No 'id' column found!")
            return

        # Step 2: Check if a sequence exists
        print("\n=== Step 2: Sequence check ===")
        r = await conn.execute(text("""
            SELECT sequence_name FROM information_schema.sequences
            WHERE sequence_name LIKE '%historical_daily%'
        """))
        seqs = [row[0] for row in r.fetchall()]
        print(f"  Sequences: {seqs}")

        # Also look for any sequence with 'id' in name
        r = await conn.execute(text("""
            SELECT sequence_name FROM information_schema.sequences
            WHERE sequence_name ~ 'historical_daily.*id|id.*historical_daily'
               OR sequence_name LIKE '%hist_daily%id%'
        """))
        more_seqs = [row[0] for row in r.fetchall()]
        print(f"  Additional sequences: {more_seqs}")

        # Step 3: Check partition column definition
        print("\n=== Step 3: Partition column definitions ===")
        r = await conn.execute(text("""
            SELECT table_name, column_name, column_default, is_identity
            FROM information_schema.columns
            WHERE table_name LIKE 'brsapi_historical_daily_%'
              AND column_name = 'id'
            LIMIT 5
        """))
        partitions = r.fetchall()
        if partitions:
            for p in partitions:
                print(f"  {p[0]}: default={p[2]}, is_identity={p[3]}")
        else:
            print("  No partition entries found in information_schema")

        # Step 4: Test INSERTs
        print("\n=== Step 4: INSERT tests ===")
        try:
            await conn.execute(text("""
                INSERT INTO brsapi_historical_daily (symbol, date, price_close)
                VALUES ('_test_sym', '1405-01-01', 1000)
            """))
            await conn.execute(text("DELETE FROM ONLY brsapi_historical_daily WHERE symbol = '_test_sym'"))
            print("  INSERT without id: SUCCESS (id auto-generated via default)")
        except Exception as e:
            print(f"  INSERT without id: FAILED - {e}")
            print("\n  >>> The id column has no working sequence default!")
            print("  >>> Need to create a sequence manually.")

            # Step 5: Create sequence manually
            print("\n=== Step 5: Creating sequence ===")
            try:
                # Create sequence if it doesn't exist
                await conn.execute(text("""
                    CREATE SEQUENCE IF NOT EXISTS brsapi_historical_daily_id_seq
                """))
                print("  Sequence created/confirmed.")

                # Set default on parent table
                await conn.execute(text("""
                    ALTER TABLE brsapi_historical_daily
                    ALTER COLUMN id SET DEFAULT nextval('brsapi_historical_daily_id_seq'::regclass)
                """))
                print("  Default set on parent table.")

                # Set the sequence to max(id) or start at 1
                r = await conn.execute(text("""
                    SELECT COALESCE(MAX(id), 0) + 1 FROM ONLY brsapi_historical_daily
                """))
                next_val = r.scalar() or 1
                await conn.execute(text(f"""
                    ALTER SEQUENCE brsapi_historical_daily_id_seq RESTART WITH {next_val}
                """))
                print(f"  Sequence starts at: {next_val}")

                # Test again
                print("\n=== Step 6: Retry INSERT ===")
                try:
                    await conn.execute(text("""
                        INSERT INTO brsapi_historical_daily (symbol, date, price_close)
                        VALUES ('_test_sym', '1405-01-01', 1000)
                    """))
                    await conn.execute(text("DELETE FROM ONLY brsapi_historical_daily WHERE symbol = '_test_sym'"))
                    print("  INSERT: SUCCESS after fix!")
                except Exception as e2:
                    print(f"  INSERT: STILL FAILED - {e2}")

            except Exception as e3:
                print(f"  Failed to create sequence: {e3}")

        print("\n=== Done ===")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
