#!/usr/bin/env python
"""Fix autoincrement for brsapi_historical_daily."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import io

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

    # Use different connections to avoid transaction issues
    # Connection 1: Create sequence and set default
    engine1 = create_async_engine(db_url, isolation_level="AUTOCOMMIT")
    async with engine1.connect() as conn:
        print("Step 1: Create sequence...")
        await conn.execute(text("""
            CREATE SEQUENCE IF NOT EXISTS brsapi_historical_daily_id_seq
        """))
        print("  Sequence created/confirmed.")

        print("Step 2: Set default on parent table...")
        await conn.execute(text("""
            ALTER TABLE brsapi_historical_daily
            ALTER COLUMN id SET DEFAULT nextval('brsapi_historical_daily_id_seq'::regclass)
        """))
        print("  Default set.")

        # Set sequence start value
        r = await conn.execute(text("""
            SELECT COALESCE(MAX(id), 0) + 1 FROM ONLY brsapi_historical_daily
        """))
        next_val = r.scalar() or 1
        await conn.execute(text(f"""
            ALTER SEQUENCE brsapi_historical_daily_id_seq RESTART WITH {next_val}
        """))
        print(f"  Sequence starts at: {next_val}")

    await engine1.dispose()

    # Connection 2: Verify and test
    engine2 = create_async_engine(db_url)
    async with engine2.begin() as conn:
        print("\nStep 3: Verify...")
        r = await conn.execute(text("""
            SELECT column_name, column_default, is_identity
            FROM information_schema.columns
            WHERE table_name = 'brsapi_historical_daily'
              AND column_name = 'id'
        """))
        row = r.fetchone()
        print(f"  Column default: {row[1]}")
        print(f"  Is identity: {row[2]}")

        # Test INSERT
        print("\nStep 4: Test INSERT...")
        await conn.execute(text("""
            INSERT INTO brsapi_historical_daily (symbol, date, price_close)
            VALUES ('_test_sym', '1405-01-01', 1000)
        """))
        print("  INSERT: SUCCESS!")

        # Clean up test row
        await conn.execute(text("""
            DELETE FROM ONLY brsapi_historical_daily WHERE symbol = '_test_sym'
        """))
        print("  Test row cleaned up.")

        # Confirm the row was inserted
        r = await conn.execute(text("""
            SELECT symbol, date, price_close, id
            FROM ONLY brsapi_historical_daily
            WHERE symbol = '_test_sym'
        """))
        inserted = r.fetchone()
        if inserted:
            print(f"  Row found: id={inserted[3]}")
        else:
            print("  Row not found (expected after delete)")

    await engine2.dispose()
    print("\nDone! The autoincrement is now working.")


if __name__ == "__main__":
    asyncio.run(main())
