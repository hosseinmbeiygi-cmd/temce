"""Finish dual-date gaps: re-enable disabled triggers + fix wrong source columns.

Found gaps (after migration 0025 + backfill_dual_dates.py + fix_dual_date_gaps.py):

- ``gold_currency_prices`` (hypertable): trg_dual_dates left DISABLED by an
  interrupted backfill -> all 74,463 rows NULL, and new inserts don't sync.
- ``indices``: registered with source ``time`` but never backfilled (4 rows).
- ``brsapi_ime_physical_trades``: source ``date_price_settlement`` is '' on 198
  rows; ``date_trade`` is populated on all rows -> switch source.
- ``codal_audit_summary``: ``report_date`` is year-only ('۱۴۰۵'); ``analyzed_at``
  is a real timestamp -> switch source.
- ``codal_financial_statements``: ``report_date`` is year-only ('۱۴۰۵');
  ``imported_at`` is a real timestamp -> switch source.
- ``brsapi_ime_futures``: ``date_end``/``date_end_text`` are '0000-00-00'/'' on
  every row (source-data garbage) -> no fix possible, left as-is.

Idempotent. Re-run after this (the direct SQL backfill handles hypertables
without trigger toggling): ``python scripts/backfill_dual_dates_direct.py``

Usage:
    python scripts/fix_dual_date_remaining.py
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from scripts._db import database_url_async

    DB_URL = database_url_async()
except ImportError:
    from _db import database_url_async

    DB_URL = database_url_async()

# (table, better source column) — populated columns chosen over empty/year-only ones
SOURCE_FIXES = {
    "brsapi_ime_physical_trades": "date_trade",
    "codal_audit_summary": "analyzed_at",
    "codal_financial_statements": "imported_at",
}


async def main() -> None:
    engine = create_async_engine(DB_URL)
    try:
        async with engine.begin() as conn:
            # 1) re-enable any disabled trg_dual_dates on public tables
            disabled = (
                await conn.execute(
                    text(
                        "SELECT pc.relname FROM pg_trigger t "
                        "JOIN pg_class pc ON pc.oid = t.tgrelid "
                        "JOIN pg_namespace pn ON pn.oid = pc.relnamespace "
                        "WHERE t.tgname = 'trg_dual_dates' AND pn.nspname = 'public' "
                        "  AND t.tgenabled = 'D' ORDER BY 1"
                    )
                )
            ).scalars().all()
            for table in disabled:
                await conn.execute(text(f'ALTER TABLE "{table}" ENABLE TRIGGER trg_dual_dates'))
                print(f"enabled trigger on {table}")

            # 2) fix source columns
            for table, src in SOURCE_FIXES.items():
                await conn.execute(
                    text("UPDATE dual_date_columns SET source_column = :s WHERE table_name = :t"),
                    {"t": table, "s": src},
                )
                print(f"source {table} -> {src}")

        # 3) sanity: triggers on hypertable chunks now enabled?
        async with engine.connect() as conn:
            n_chunks_off = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM pg_trigger t "
                        "JOIN pg_class pc ON pc.oid = t.tgrelid "
                        "JOIN pg_namespace pn ON pn.oid = pc.relnamespace "
                        "WHERE t.tgname = 'trg_dual_dates' AND pn.nspname = '_timescaledb_internal' "
                        "  AND t.tgenabled = 'D'"
                    )
                )
            ).scalar()
            print(f"disabled chunk triggers remaining: {n_chunks_off}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
