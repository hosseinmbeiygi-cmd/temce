"""
Add TIMESTAMPTZ columns (trade_date_utc / fetched_at_utc) to the main
brsapi_* tables and backfill them from the existing VARCHAR Shamsi dates
using ``jdatetime`` (the project's available library — there is no
``persian_to_gregorian`` helper in the codebase).

Design:
  * ``ALTER TABLE ADD COLUMN`` (instant in PG11+ when the column is NULL)
  * Batch UPDATE of 1,000 rows per transaction → no long table lock
  * Idempotent — re-running only fills remaining NULLs
  * SQLAlchemy 2.0 + AsyncPG

Usage:
    python scripts/backfill_dates.py
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
from datetime import datetime, timezone
from typing import Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import jdatetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Config ──────────────────────────────────────────────────────────────────
# Credentials come from settings/.env — never hardcode them in scripts.
try:
    from scripts._db import database_url_async

    DATABASE_URL = database_url_async()
except Exception:  # pragma: no cover
    DATABASE_URL = os.environ.get("DATABASE_URL")
BATCH_SIZE = 1000

# (table, new TIMESTAMPTZ column, source column, is_shamsi_date)
#   is_shamsi=True  → source is a Shamsi "YYYY-MM-DD" string → convert via jdatetime
#   is_shamsi=False → source is already a timestamp/datetime → normalize to UTC
TABLES: list[tuple[str, str, str, bool]] = [
    ("brsapi_historical_daily",      "trade_date_utc",  "date",         True),
    ("brsapi_intraday_trades",       "trade_date_utc",  "date",         True),
    ("brsapi_codal_announcements",   "date_publish_utc","date_publish", True),
    ("brsapi_symbol_snapshots",      "fetched_at_utc",  "created_at",   False),
    ("brsapi_candlesticks",          "fetched_at_utc",  "time",         False),
]


def shamsi_to_gregorian_utc(value: Any) -> datetime | None:
    """Convert a Shamsi 'YYYY-MM-DD' string to an aware UTC datetime at 00:00."""
    if not value:
        return None
    s = str(value).strip()
    try:
        y, m, d = (int(p) for p in s.split("-"))
        g = jdatetime.date(y, m, d).togregorian()
        return datetime(g.year, g.month, g.day, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def to_utc(value: Any) -> datetime | None:
    """Normalize a naive/aware datetime to UTC (used for non-Shamsi sources)."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def ensure_column(session: AsyncSession, table: str, column: str) -> bool:
    """Add the TIMESTAMPTZ column if missing. Returns True when freshly added."""
    exists = await session.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column},
    )
    if exists.scalar():
        return False
    await session.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" TIMESTAMPTZ'))
    await session.commit()
    print(f"  + {table}.{column} column added")
    return True


async def backfill(
    session_factory: async_sessionmaker[AsyncSession],
    table: str,
    target: str,
    source: str,
    is_shamsi: bool,
) -> None:
    async with session_factory() as session:
        nulls = (
            await session.execute(
                text(f'SELECT count(*) FROM "{table}" WHERE "{target}" IS NULL')
            )
        ).scalar()
        if nulls == 0:
            print(f"  ✓ {table}.{target}: nothing to fill")
            return

        print(f"  … {table}.{target}: {nulls:,} NULLs to fill from {source}")
        done = 0
        while True:
            async with session_factory() as s:
                rows = (
                    await s.execute(
                        text(
                            f'SELECT id, "{source}" AS src FROM "{table}" '
                            f'WHERE "{target}" IS NULL AND "{source}" IS NOT NULL '
                            f"ORDER BY id LIMIT {BATCH_SIZE}"
                        )
                    )
                ).fetchall()
                if not rows:
                    break
                for rid, src in rows:
                    utc = shamsi_to_gregorian_utc(src) if is_shamsi else to_utc(src)
                    if utc is not None:
                        await s.execute(
                            text(f'UPDATE "{table}" SET "{target}" = :v WHERE id = :i'),
                            {"v": utc, "i": rid},
                        )
                await s.commit()
            done += len(rows)
            if done % (BATCH_SIZE * 10) == 0 or done >= nulls:
                print(f"    {table}.{target}: {done:,}/{nulls:,} ({done * 100 // nulls}%)")
        print(f"  ✓ {table}.{target}: {done:,} rows backfilled")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    for table, target, source, is_shamsi in TABLES:
        print(f"\n== {table} ==")
        async with session_factory() as session:
            added = await ensure_column(session, table, target)
        if added:
            await backfill(session_factory, table, target, source, is_shamsi)
    await engine.dispose()
    print("\n✅ Backfill complete")


if __name__ == "__main__":
    asyncio.run(main())