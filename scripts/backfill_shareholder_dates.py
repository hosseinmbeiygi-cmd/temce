"""Backfill ``brsapi_shareholder_records.date`` for rows where it is NULL.

``Shareholder.php`` returns the LATEST composition and carries no ``date``
field, so rows synced without a ``date`` param end up with ``date IS NULL``
(7,478 rows at the time of writing). This script stamps the **fetch date**
(``created_at``) onto those rows, in the same Gregorian ``YYYY-MM-DD`` format
the already-populated ``date`` values use.

Because the table has a UNIQUE constraint on ``(symbol, shareholder_name,
date)`` (added by ``scripts/import_shareholders.py``), rows fetched more than
once on the SAME day would collide after stamping. The script therefore:

1. Removes the OLDER duplicate NULL rows per ``(symbol, shareholder_name,
   fetch-day)`` — keeping the newest snapshot of each day;
2. Removes NULL rows whose fetch-day already has an official DATED row (the
   dated row wins);
3. Stamps the remaining NULL rows with ``to_char(created_at, 'YYYY-MM-DD')``.

``created_at`` is a naive local timestamp and the dual-date trigger derives
``gregorian_date``/``shamsi_date`` from it the same way, so the stamped value
stays consistent with the dual-date columns.

Idempotent — re-running is a no-op once no NULL rows remain.

Note: ``sync_shareholders`` (the daily 13:30 job / manual backfill path) now
stamps the fetch date on new rows too (and the generic ``ON CONFLICT DO
NOTHING`` bulk insert dedupes same-day re-syncs), so this problem does not
recur.

Usage:
    python scripts/backfill_shareholder_dates.py
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from scripts._db import database_url_async

    DB_URL = database_url_async()
except ImportError:
    from _db import database_url_async

    DB_URL = database_url_async()

# Same fetch-day duplicates (same symbol + shareholder + created_at date) are
# redundant snapshots — keep the newest (created_at, id) per group so the
# UNIQUE (symbol, shareholder_name, date) constraint can be satisfied.
DEDUP_SQL = text(
    """
    DELETE FROM brsapi_shareholder_records a
    USING brsapi_shareholder_records b
    WHERE a.date IS NULL AND b.date IS NULL
      AND a.symbol = b.symbol
      AND a.shareholder_name = b.shareholder_name
      AND to_char(a.created_at, 'YYYY-MM-DD') = to_char(b.created_at, 'YYYY-MM-DD')
      AND (a.created_at < b.created_at OR (a.created_at = b.created_at AND a.id < b.id))
    """
)

# NULL rows whose fetch-day already has an official DATED row would collide
# on UPDATE — the dated row (explicitly fetched for that date) wins.
DATED_COLLISION_SQL = text(
    """
    DELETE FROM brsapi_shareholder_records a
    USING brsapi_shareholder_records b
    WHERE a.date IS NULL AND b.date IS NOT NULL
      AND a.symbol = b.symbol
      AND a.shareholder_name = b.shareholder_name
      AND b.date = to_char(a.created_at, 'YYYY-MM-DD')
    """
)

UPDATE_SQL = text(
    """
    UPDATE brsapi_shareholder_records
    SET date = to_char(created_at, 'YYYY-MM-DD')
    WHERE date IS NULL
    """
)


async def main() -> None:
    engine = create_async_engine(DB_URL)
    try:
        async with engine.begin() as conn:
            deduped = await conn.execute(DEDUP_SQL)
            print(
                f"Removed {deduped.rowcount} duplicate NULL-date rows "
                "(same symbol + shareholder + fetch-day)"
            )
        async with engine.begin() as conn:
            collided = await conn.execute(DATED_COLLISION_SQL)
            print(
                f"Removed {collided.rowcount} NULL-date rows superseded by an "
                "official dated row for the same day"
            )

        async with engine.begin() as conn:
            updated = await conn.execute(UPDATE_SQL)
            print(f"Stamped {updated.rowcount} rows with the fetch date (created_at)")

        async with engine.connect() as conn:
            remaining = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM brsapi_shareholder_records "
                        "WHERE date IS NULL"
                    )
                )
            ).scalar()
            print(f"Remaining NULL dates: {remaining}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
