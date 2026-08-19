"""Direct SQL backfill of dual-date columns (no trigger toggling).

The streaming backfill (backfill_dual_dates.py) hung on the TimescaleDB
hypertable ``gold_currency_prices`` (trigger left disabled after a hard kill).
This script updates rows with pure SQL using the same conversion functions
installed by scripts/install_dual_dates.py, so the BEFORE trigger never needs
disabling (recomputing from the source column is idempotent — the trigger
fires on the UPDATE but re-derives the same values).

Unlike the streaming script it evaluates ``any_to_miladi`` once per row and
persists the same ``scripts/.dual_dates_progress.json`` so both backfill tools
stay consistent.

Usage:
    python scripts/backfill_dual_dates_direct.py                # all tables
    python scripts/backfill_dual_dates_direct.py trades,quotes  # only those
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from scripts._db import database_url_async

    DB_URL = database_url_async()
except ImportError:
    from _db import database_url_async

    DB_URL = database_url_async()

PROGRESS_FILE = Path(__file__).resolve().parent / ".dual_dates_progress.json"


def _load_progress() -> dict[str, str]:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_progress(progress: dict[str, str]) -> None:
    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


async def backfill_table(engine, table: str, src: str) -> int:
    # evaluate any_to_miladi once per row via a lateral subselect
    stmt = text(
        f'UPDATE "{table}" SET '
        f"gregorian_date = x.mil, "
        f"shamsi_date = CASE WHEN x.mil IS NULL THEN NULL ELSE miladi_to_shamsi(x.mil) END "
        f"FROM (SELECT any_to_miladi(\"{src}\"::text) AS mil) x "
        f'WHERE gregorian_date IS NULL AND "{src}" IS NOT NULL'
    )
    async with engine.begin() as conn:
        result = await conn.execute(stmt)
        return result.rowcount or 0


async def main(only: set[str] | None, force: bool) -> None:
    engine = create_async_engine(DB_URL)
    progress = _load_progress()
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(text("SELECT table_name, source_column FROM dual_date_columns ORDER BY table_name"))
            ).fetchall()
        for table, src in rows:
            if only is not None and table not in only:
                continue
            if not force and progress.get(table) == "ok":
                print(f"skip {table} (already done)")
                continue
            try:
                n = await backfill_table(engine, table, src)
                progress[table] = "ok"
                _save_progress(progress)
                print(f"  {table}: updated {n:,} rows (src={src})")
            except Exception as exc:
                progress[table] = f"error: {exc}"
                _save_progress(progress)
                print(f"  {table}: ERROR {type(exc).__name__}: {str(exc)[:150]}", file=sys.stderr)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Direct SQL dual-date backfill")
    parser.add_argument("tables", nargs="?", default="", help="comma-separated table names (default: all)")
    parser.add_argument("--force", action="store_true", help="re-process tables marked done")
    args = parser.parse_args()
    only = {t.strip() for t in args.tables.split(",") if t.strip()} or None
    asyncio.run(main(only, args.force))
