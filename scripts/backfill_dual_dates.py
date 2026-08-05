"""Backfill ``gregorian_date`` / ``shamsi_date`` on every table.

Run this after ``alembic upgrade head`` (migration 0025 installs the schema
and triggers but deliberately skips the data backfill so huge tables are not
locked for a long time).

Strategy:
  - source column comes from the ``dual_date_columns`` meta table
  - conversion is done in Python with ``jdatetime`` (the same reference the
    SQL functions were validated against)
  - rows are streamed and updated in batches of 5000 keyed by the table PK
  - the per-table trigger is disabled/enabled through *separate* connections
    (asyncpg raises ObjectInUseError when DDL runs on a connection with an
    active stream cursor)
  - one commit per table; progress is recorded in
    ``scripts/.dual_dates_progress.json`` so the script is resumable

Usage:
    python scripts/backfill_dual_dates.py                # all tables
    python scripts/backfill_dual_dates.py --only trades,quotes
    python scripts/backfill_dual_dates.py --force        # redo finished tables
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import re
import sys
from pathlib import Path

import jdatetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

try:
    from scripts._db import database_url_async

    DB_URL = database_url_async()
except Exception:  # pragma: no cover
    DB_URL = os.environ.get("DATABASE_URL")

PROGRESS_FILE = Path(__file__).resolve().parent / ".dual_dates_progress.json"
BATCH = 20000
FETCH = 20000

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_DATE_RE = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$")


def _convert(value) -> tuple[datetime.date | None, str | None]:
    """Convert any stored date-ish value to (gregorian date, shamsi string)."""
    if value is None:
        return None, None
    s = str(value).strip()
    if not s:
        return None, None
    s = s.translate(_DIGITS).strip("'").strip()
    if len(s) > 10 and re.match(r"^\d{4}-\d{1,2}-\d{1,2}[T ]", s):
        s = s[:10]
    m = _DATE_RE.match(s)
    if not m:
        return None, None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        g = datetime.date(y, mo, d) if 1800 <= y <= 2200 else jdatetime.date(y, mo, d).togregorian()
        j = jdatetime.date.fromgregorian(date=g)
        return g, f"{j.year}-{j.month:02d}-{j.day:02d}"
    except (ValueError, OverflowError):
        return None, None


def _load_progress() -> dict[str, str]:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_progress(progress: dict[str, str]) -> None:
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


async def _backfill_table(engine: AsyncEngine, table: str, src: str, pk_cols: list[str]) -> int:
    """Stream rows, convert and batch-update. Returns number of rows updated."""
    cols_sql = ", ".join(f'"{c}"' for c in pk_cols)
    where_sql = " AND ".join(f'"{c}" = :p{i}' for i, c in enumerate(pk_cols))

    # disable the trigger through a separate connection
    async with engine.begin() as ddl:
        await ddl.execute(text(f'ALTER TABLE "{table}" DISABLE TRIGGER trg_dual_dates'))

    total = 0
    batch: list[dict] = []
    try:
        async with engine.begin() as conn:
            result = await conn.stream(
                text(f'SELECT {cols_sql}, "{src}"::text AS v FROM "{table}" WHERE "{src}" IS NOT NULL')
            )
            try:
                while True:
                    rows = await result.fetchmany(FETCH)
                    if not rows:
                        break
                    for row in rows:
                        pk_vals = list(row)[:-1]
                        g, s = _convert(row[-1])
                        if g is None:
                            continue
                        params = {f"p{i}": val for i, val in enumerate(pk_vals)}
                        params.update({"g": g, "s": s})
                        batch.append(params)
                        if len(batch) >= BATCH:
                            await conn.execute(
                                text(f'UPDATE "{table}" SET gregorian_date = :g, shamsi_date = :s WHERE {where_sql}'),
                                batch,
                            )
                            total += len(batch)
                            batch = []
                            print(f"  {table}: {total:,} rows...", end="\r")
            finally:
                await result.close()
            if batch:
                await conn.execute(
                    text(f'UPDATE "{table}" SET gregorian_date = :g, shamsi_date = :s WHERE {where_sql}'),
                    batch,
                )
                total += len(batch)
            # engine.begin() commits the update transaction here
    finally:
        async with engine.begin() as ddl2:
            await ddl2.execute(text(f'ALTER TABLE "{table}" ENABLE TRIGGER trg_dual_dates'))
    return total


async def main(only: set[str] | None, force: bool) -> None:
    engine = create_async_engine(DB_URL)
    progress = _load_progress()
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(text("SELECT table_name, source_column FROM dual_date_columns ORDER BY table_name"))
            ).fetchall()
            targets = [(r[0], r[1]) for r in rows if only is None or r[0] in only]

            pk_rows = (
                await conn.execute(
                    text(
                        "SELECT tc.table_name, string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) "
                        "FROM information_schema.table_constraints tc "
                        "JOIN information_schema.key_column_usage kcu "
                        "  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema "
                        "WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public' "
                        "GROUP BY tc.table_name"
                    )
                )
            ).fetchall()
            pks = {r[0]: r[1].split(",") for r in pk_rows}

        for table, src in targets:
            if not force and progress.get(table) == "ok":
                print(f"skip {table} (already done)")
                continue
            pk_cols = pks.get(table)
            if not pk_cols:
                print(f"skip {table} (no PK)")
                continue
            print(f"backfilling {table} (src={src}, pk={pk_cols})")
            try:
                n = await _backfill_table(engine, table, src, pk_cols)
                progress[table] = "ok"
                _save_progress(progress)
                print(f"  {table}: {n:,} rows -> OK")
            except Exception as exc:  # keep going with the next table
                progress[table] = f"error: {exc}"
                _save_progress(progress)
                print(f"  {table}: ERROR {type(exc).__name__}: {str(exc)[:160]}", file=sys.stderr)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill dual-date columns")
    parser.add_argument("--only", help="comma-separated table names to process")
    parser.add_argument("--force", action="store_true", help="re-process tables marked done")
    args = parser.parse_args()
    only = {t.strip() for t in args.only.split(",") if t.strip()} if args.only else None
    asyncio.run(main(only, args.force))
