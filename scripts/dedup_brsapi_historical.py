#!/usr/bin/env python3
"""Batch deduplication of brsapi_historical_daily.

Strategy:
  1. Process one day (chunk) at a time to avoid long locks.
  2. Within each day, keep the row with the highest `id` (newest).
  3. Delete duplicates in batches of 5000 ctids.
  4. After all chunks are clean, create a unique index CONCURRENTLY.
  5. Report progress every N chunks.

Resumable: if interrupted, rerun — already-clean days are skipped.
"""

from __future__ import annotations

import os
import time

import psycopg2

BATCH_SIZE = 5000  # rows deleted per transaction


def get_conn() -> psycopg2.extensions.connection:
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


def count_duplicates_for_day(cur, day: str) -> int:
    """Count how many duplicate rows exist for a given date."""
    cur.execute(
        """
        SELECT COUNT(*) - COUNT(DISTINCT symbol)
        FROM brsapi_historical_daily
        WHERE date = %s
    """,
        (day,),
    )
    return cur.fetchone()[0]


def delete_duplicates_for_day(cur, day: str) -> int:
    """Delete duplicates for a single day, keeping the row with max id.

    Returns the number of rows deleted.
    """
    total_deleted = 0

    while True:
        # Find ctids of duplicates to delete (keep max id per symbol)
        cur.execute(
            """
            DELETE FROM brsapi_historical_daily
            WHERE ctid IN (
                SELECT ctid FROM (
                    SELECT ctid,
                           ROW_NUMBER() OVER (
                               PARTITION BY symbol
                               ORDER BY id DESC
                           ) AS rn
                    FROM brsapi_historical_daily
                    WHERE date = %s
                ) sub
                WHERE rn > 1
                LIMIT %s
            )
        """,
            (day, BATCH_SIZE),
        )
        deleted = cur.rowcount
        total_deleted += deleted
        if deleted == 0:
            break

    return total_deleted


def main() -> None:
    conn = get_conn()

    print("=== brsapi_historical_daily batch dedup ===")

    # Phase 1: Discovery (autocommit=True for speed)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET statement_timeout = 60000")

    cur.execute("SELECT COUNT(DISTINCT date::text) FROM brsapi_historical_daily")
    num_days = cur.fetchone()[0]
    print(f"Total distinct days: {num_days}")

    # Use a heuristic: check a few sample days to estimate
    cur.execute("SELECT DISTINCT date::text FROM brsapi_historical_daily ORDER BY date LIMIT 5")
    sample_days = [row[0] for row in cur.fetchall()]
    sample_dups = 0
    for d in sample_days:
        cur.execute("SELECT COUNT(*) - COUNT(DISTINCT symbol) FROM brsapi_historical_daily WHERE date = %s", (d,))
        sample_dups += cur.fetchone()[0]
    avg_dups = sample_dups / len(sample_days) if sample_days else 0
    est_total_dups = int(avg_dups * num_days)
    print(f"Estimated total duplicates: ~{est_total_dups:,} (from {len(sample_days)}-day sample)")
    print(f"Estimated rows after dedup: ~{5_600_000 - est_total_dups:,}")
    cur.close()

    # Phase 2: Batch dedup (autocommit=False)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SET statement_timeout = 30000")

    # Get all distinct dates
    cur.execute("SELECT DISTINCT date::text FROM brsapi_historical_daily ORDER BY date")
    days = [row[0] for row in cur.fetchall()]
    conn.commit()  # end the SELECT transaction

    print(f"Processing {len(days)} days...")
    print()

    start = time.time()
    total_deleted = 0
    clean_count = 0
    for i, day in enumerate(days, 1):
        deleted = delete_duplicates_for_day(cur, day)
        conn.commit()
        total_deleted += deleted
        if deleted == 0:
            clean_count += 1
        elapsed = time.time() - start
        rate = total_deleted / elapsed if elapsed > 0 else 0
        remaining_est = est_total_dups - total_deleted
        eta = remaining_est / rate if rate > 0 else 0
        if i % 100 == 0 or i == len(days) or deleted > 100:
            print(
                f"  [{i}/{len(days)}] {day}: del={deleted} | "
                f"total {total_deleted:,} | "
                f"rate {rate:,.0f}/s | ETA {eta / 60:.1f}m"
            )

    elapsed = time.time() - start
    print(f"\nDedup complete: {total_deleted:,} rows deleted in {elapsed / 60:.1f}m")
    print(f"Days with no dups (skipped): {clean_count}/{len(days)}")

    # Phase 3: Verify
    cur.execute("SET statement_timeout = 60000")
    cur.execute("SELECT COUNT(*) FROM brsapi_historical_daily")
    final_count = cur.fetchone()[0]
    print(f"Final row count: {final_count:,}")
    cur.close()
    conn.commit()

    # Phase 4: Create unique index
    _create_unique_index(conn)

    conn.close()


def _create_unique_index(conn) -> None:
    """Create the unique index on (symbol, date)."""
    cur = conn.cursor()
    # Check if already exists
    cur.execute(
        """
        SELECT 1 FROM pg_indexes
        WHERE tablename='brsapi_historical_daily'
          AND indexname='uq_brsapi_historical_daily_symbol_date'
    """
    )
    if cur.fetchone():
        print("Unique index already exists")
        return

    print("Creating unique index (may take a few minutes)...")
    conn.autocommit = True
    try:
        cur.execute(
            """
            CREATE UNIQUE INDEX CONCURRENTLY
                uq_brsapi_historical_daily_symbol_date
            ON brsapi_historical_daily (symbol, date)
        """
        )
        print("✅ Unique index created successfully")
    except Exception as ex:
        print(f"⚠️ Index creation failed: {ex}")
        print("   Run manually: CREATE UNIQUE INDEX CONCURRENTLY ...")


if __name__ == "__main__":
    main()
