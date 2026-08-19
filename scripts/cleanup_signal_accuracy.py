"""Clean up the polluted signal_accuracy table.

The persistence bug inserted a NEW row for the same signal on every pipeline
run (every cache TTL), so one signal could have hundreds/thousands of pending
duplicates (e.g. BRENT buy x2872). Those duplicates flooded the evaluation
queue and skewed accuracy stats toward whatever signal happened to be first.

This script:
  1. Deletes duplicate PENDING rows (outcome_set_at IS NULL), keeping only the
     OLDEST row per (symbol, market, direction, timeframe).
  2. Deletes pending hold/wait rows (they have no tradable outcome and were
     persisted before the persistence fix).
  3. Deletes pending rows older than 35 days — the evaluation sweep only picks
     signals 5-30 days old, so older pending rows are orphans.

Usage:
    python scripts/cleanup_signal_accuracy.py   # --dry-run by default
    python scripts/cleanup_signal_accuracy.py --apply
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings

APPLY = "--apply" in sys.argv


async def main() -> None:
    dsn = settings.database_url_async or settings.database_url
    engine = create_async_engine(dsn)
    async with engine.connect() as conn:
        # 1. duplicate pending rows: keep the oldest per key
        r = await conn.execute(text("""
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol, market, direction, timeframe
                           ORDER BY generated_at ASC, id ASC
                       ) AS rn
                FROM signal_accuracy
                WHERE outcome_set_at IS NULL
            )
            SELECT COUNT(*) FROM ranked WHERE rn > 1
        """))
        dupes = r.scalar() or 0

        # 2. pending hold/wait rows
        r = await conn.execute(text("""
            SELECT COUNT(*) FROM signal_accuracy
            WHERE outcome_set_at IS NULL AND direction IN ('hold', 'wait')
        """))
        holds = r.scalar() or 0

        # 3. stale pending rows (>35 days old, outside the 5-30d eval window)
        r = await conn.execute(text("""
            SELECT COUNT(*) FROM signal_accuracy
            WHERE outcome_set_at IS NULL
              AND generated_at < NOW() - INTERVAL '35 days'
        """))
        stale = r.scalar() or 0

        print(f"To remove: {dupes} duplicate-pending | {holds} hold/wait pending | {stale} stale pending")

        if not APPLY:
            print("DRY-RUN: pass --apply to execute the deletes.")
            await engine.dispose()
            return

        async with engine.begin() as txn:
            # duplicate pending (keep oldest per key)
            r = await txn.execute(text("""
                WITH ranked AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY symbol, market, direction, timeframe
                               ORDER BY generated_at ASC, id ASC
                           ) AS rn
                    FROM signal_accuracy
                    WHERE outcome_set_at IS NULL
                )
                DELETE FROM signal_accuracy sa
                USING ranked
                WHERE sa.id = ranked.id AND ranked.rn > 1
            """))
            print(f"Deleted {r.rowcount} duplicate pending rows")

            # hold/wait pending
            r = await txn.execute(text("""
                DELETE FROM signal_accuracy
                WHERE outcome_set_at IS NULL AND direction IN ('hold', 'wait')
            """))
            print(f"Deleted {r.rowcount} hold/wait pending rows")

            # stale pending
            r = await txn.execute(text("""
                DELETE FROM signal_accuracy
                WHERE outcome_set_at IS NULL
                  AND generated_at < NOW() - INTERVAL '35 days'
            """))
            print(f"Deleted {r.rowcount} stale pending rows")

        # summary after
        r = await conn.execute(text("""
            SELECT COUNT(*),
                   SUM(CASE WHEN outcome_set_at IS NULL THEN 1 ELSE 0 END)
            FROM signal_accuracy
        """))
        total, pending = r.fetchone()
        print(f"After cleanup: {total} total rows, {pending} pending")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
