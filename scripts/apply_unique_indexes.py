"""
Deduplicate brsapi_historical_daily and create a UNIQUE INDEX on (symbol, date)
using CONCURRENTLY (zero-downtime, no table lock).

Important
---------
The table has **~525,970 duplicate (symbol, date) pairs** as of the last
check — the unique index WILL fail until those are cleaned up.

Strategy
--------
1. Identify duplicates: keep the NEWEST row per (symbol, date) by id.
2. DELETE older duplicates in batches (1,000 at a time) to avoid long locks.
3. CREATE UNIQUE INDEX CONCURRENTLY (outside a transaction — this step
   MUST be run via ``op.execute("COMMIT")`` + raw SQL, or from a script
   that does not wrap in a transaction).

Usage
-----
    python scripts/apply_unique_indexes.py

Rollback
--------
    DROP INDEX IF EXISTS uq_brsapi_historical_daily_symbol_date;
"""

from __future__ import annotations

import asyncio
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = "postgresql+asyncpg://hossein:1343@localhost:5432/my_first_db"
DELETE_BATCH = 1000
INDEX_NAME = "uq_brsapi_historical_daily_symbol_date"
TABLE = "brsapi_historical_daily"


async def check_duplicates(session: AsyncSession) -> int:
    """Return the number of duplicate (symbol, date) groups."""
    result = await session.execute(
        text(
            "SELECT count(*) FROM ("
            f"  SELECT symbol, date, count(*) c FROM {TABLE} "
            "  GROUP BY symbol, date HAVING count(*) > 1"
            ") d"
        )
    )
    return result.scalar()


async def deduplicate(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Delete older duplicates in batches, keeping the newest row per group."""
    total_deleted = 0
    while True:
        async with session_factory() as session:
            # Find the next batch of duplicate IDs to delete (keep the max id)
            batch = await session.execute(
                text(
                    f"DELETE FROM {TABLE} "
                    "WHERE id IN ("
                    "  SELECT id FROM ("
                    "    SELECT id, row_number() OVER ("
                    "      PARTITION BY symbol, date ORDER BY id DESC"
                    f"    ) AS rn FROM {TABLE}"
                    "  ) ranked WHERE rn > 1"
                    f"  LIMIT {DELETE_BATCH}"
                    ")"
                    "RETURNING id"
                )
            )
            deleted = len(batch.fetchall())
            await session.commit()
        if deleted == 0:
            break
        total_deleted += deleted
        print(f"  Deleted {total_deleted:,} duplicate rows...")
    return total_deleted


async def index_exists(session: AsyncSession) -> bool:
    result = await session.execute(
        text(
            "SELECT 1 FROM pg_indexes WHERE tablename=:t AND indexname=:i"
        ),
        {"t": TABLE, "i": INDEX_NAME},
    )
    return result.scalar() is not None


async def main() -> None:
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        if await index_exists(session):
            print(f"✓ Index {INDEX_NAME} already exists")
            await engine.dispose()
            return

        dup_groups = await check_duplicates(session)
        print(f"Found {dup_groups:,} duplicate (symbol, date) groups")

    if dup_groups > 0:
        print("Deduplicating...")
        deleted = await deduplicate(session_factory)
        print(f"✓ Deleted {deleted:,} duplicate rows")

    # CREATE INDEX CONCURRENTLY requires running outside a transaction.
    # We use the raw asyncpg driver to bypass SQLAlchemy's transactional
    # wrapping.  The engine is disposed after the direct connection closes.
    print(f"Creating UNIQUE INDEX {INDEX_NAME} CONCURRENTLY...")
    import asyncpg

    conn = await asyncpg.connect(DATABASE_URL.replace("+asyncpg", ""))
    try:
        await conn.execute(
            f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} "
            f"ON {TABLE} USING btree (symbol, date)"
        )
        print(f"✓ Index {INDEX_NAME} created successfully")
    except Exception as exc:
        print(f"✗ Index creation failed: {exc}")
        print("  Common causes:")
        print("  - Duplicate rows still exist → run dedup again")
        print("  - Concurrent write conflicts → retry later")
        print("  - Another CREATE INDEX CONCURRENTLY running → wait for it")
    finally:
        await conn.close()

    await engine.dispose()
    print("Done")


if __name__ == "__main__":
    asyncio.run(main())