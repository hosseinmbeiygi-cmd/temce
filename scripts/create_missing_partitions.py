#!/usr/bin/env python
"""Create missing yearly partitions for brsapi_historical_daily."""
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
    engine = create_async_engine(db_url, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        # Check existing partitions
        r = await conn.execute(text("""
            SELECT p.relname
            FROM pg_class p
            JOIN pg_inherits i ON p.oid = i.inhrelid
            JOIN pg_class parent ON i.inhparent = parent.oid
            WHERE parent.relname = 'brsapi_historical_daily'
        """))
        existing = {row[0] for row in r.fetchall()}
        print(f"Existing partitions ({len(existing)}): {sorted(existing)}")

        # Create yearly partitions for 1380-1406
        created = 0
        for year in range(1380, 1407):
            next_year = year + 1
            part_name = f"brsapi_historical_daily_{year}"

            if part_name in existing:
                print(f"  ✓ {part_name} already exists")
                continue

            print(f"  → Creating {part_name} (FROM '{year}-01-01' TO '{next_year}-01-01')...")
            try:
                await conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {part_name}
                    PARTITION OF brsapi_historical_daily
                    FOR VALUES FROM ('{year}-01-01') TO ('{next_year}-01-01')
                """))
                print("    ✅ Created")
                created += 1
            except Exception as e:
                print(f"    ❌ Error: {e}")

        # Also create a DEFAULT partition for any dates outside the range
        try:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS brsapi_historical_daily_default
                PARTITION OF brsapi_historical_daily DEFAULT
            """))
            print("\n  ✅ DEFAULT partition created")
        except Exception as e:
            print(f"\n  ℹ️  DEFAULT partition: {e}")

        print(f"\n✨ Done! Created {created} new partitions.")

        # Verify final count
        r = await conn.execute(text("""
            SELECT p.relname
            FROM pg_class p
            JOIN pg_inherits i ON p.oid = i.inhrelid
            JOIN pg_class parent ON i.inhparent = parent.oid
            WHERE parent.relname = 'brsapi_historical_daily'
            ORDER BY p.relname
        """))
        final = [row[0] for row in r.fetchall()]
        print(f"Total partitions now: {len(final)}")
        print(f"Partitions: {final}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
