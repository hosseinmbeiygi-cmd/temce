#!/usr/bin/env python
"""Check partition structure for brsapi_historical_daily."""
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
        # Check if table is partitioned
        r = await conn.execute(text("""
            SELECT relname, relkind
            FROM pg_class
            WHERE relname IN ('brsapi_historical_daily', 'brsapi_historical_real_legal')
        """))
        print("=== Table type ===")
        for row in r:
            kind = {'r': 'regular', 'p': 'partitioned', 'i': 'index'}.get(row[1], row[1])
            print(f"  {row[0]}: {kind}")

        # List partitions
        r = await conn.execute(text("""
            SELECT
                p.relname AS partition_name,
                pg_get_expr(p.relpartbound, p.oid) AS partition_bound
            FROM pg_class p
            JOIN pg_inherits i ON p.oid = i.inhrelid
            JOIN pg_class parent ON i.inhparent = parent.oid
            WHERE parent.relname = 'brsapi_historical_daily'
            ORDER BY p.relname
        """))
        print("\n=== Partitions for brsapi_historical_daily ===")
        partitions = r.fetchall()
        if partitions:
            for row in partitions:
                print(f"  {row[0]}: {row[1]}")
        else:
            print("  (no partitions - table might not be partitioned)")

        # Also check historical_real_legal partitions
        r = await conn.execute(text("""
            SELECT
                p.relname AS partition_name,
                pg_get_expr(p.relpartbound, p.oid) AS partition_bound
            FROM pg_class p
            JOIN pg_inherits i ON p.oid = i.inhrelid
            JOIN pg_class parent ON i.inhparent = parent.oid
            WHERE parent.relname = 'brsapi_historical_real_legal'
            ORDER BY p.relname
        """))
        print("\n=== Partitions for brsapi_historical_real_legal ===")
        partitions_rl = r.fetchall()
        if partitions_rl:
            for row in partitions_rl:
                print(f"  {row[0]}: {row[1]}")
        else:
            print("  (no partitions - table might not be partitioned)")

        # Check shareholder_records columns
        r = await conn.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'brsapi_shareholder_records'
            ORDER BY ordinal_position
        """))
        print("\n=== Shareholder records columns ===")
        for row in r:
            print(f"  {row[0]} ({row[1]})")

        # Check historical_daily columns
        r = await conn.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'brsapi_historical_daily'
            ORDER BY ordinal_position
        """))
        print("\n=== historical_daily columns ===")
        for row in r:
            print(f"  {row[0]} ({row[1]})")

        # Test INSERT into historical_daily directly (dry run)
        print("\n=== Testing INSERT compatibility ===")
        try:
            await conn.execute(text("""
                INSERT INTO brsapi_historical_daily (symbol, date, price_close)
                VALUES ('TEST', '1405-04-17', 1000)
                ON CONFLICT (id, date) DO NOTHING
            """))
            print("  ✅ INSERT with date=1405-04-17 succeeded")
            # Clean up
            await conn.execute(text("""
                DELETE FROM ONLY brsapi_historical_daily WHERE symbol = 'TEST'
            """))
        except Exception as e:
            print(f"  ❌ INSERT failed: {e}")

            # If partition doesn't exist, try creating it
            if "no partition" in str(e) or "range" in str(e).lower():
                print("\n  → Trying to create partition for 1405...")
                try:
                    # Check if partition already exists
                    r = await conn.execute(text("""
                        SELECT EXISTS (
                            SELECT 1 FROM pg_class WHERE relname = 'brsapi_historical_daily_1405'
                        )
                    """))
                    exists = r.scalar()
                    if not exists:
                        print("  → Creating partition brsapi_historical_daily_1405...")
                        await conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS brsapi_historical_daily_1405
                            PARTITION OF brsapi_historical_daily
                            FOR VALUES FROM ('1405-01-01') TO ('1406-01-01')
                        """))
                        print("  ✅ Partition created!")
                    else:
                        print("  → Partition 1405 already exists but has different boundary")
                        # Check the boundary
                        r = await conn.execute(text("""
                            SELECT pg_get_expr(p.relpartbound, p.oid)
                            FROM pg_class p
                            WHERE p.relname = 'brsapi_historical_daily_1405'
                        """))
                        print(f"  Current boundary: {r.scalar()}")
                except Exception as e2:
                    print(f"  ❌ Failed to create partition: {e2}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
