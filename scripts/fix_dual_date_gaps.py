"""Fix dual-date gaps: add source+trigger for tables the migration missed.

Migration 0025 only considered columns named ``*_date``/``date`` or a fixed
priority list, so tables whose time column is called ``time``, ``timestamp``,
``triggered_at``, ``checked_at`` or ``last_trained_at`` got the dual columns
but no ``dual_date_columns`` entry, no trigger and no backfill.

This script is idempotent — safe to re-run. For every public table that has
``gregorian_date``/``shamsi_date`` but no ``dual_date_columns`` entry it picks
a source column with a broadened heuristic (mirrors migration 0025 plus
``*_at`` / ``time`` / ``timestamp`` fallbacks) and creates the trigger.

Usage:
    python scripts/fix_dual_date_gaps.py
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from scripts._db import database_url_async

    DB_URL = database_url_async()
except Exception:  # pragma: no cover
    import os

    DB_URL = os.environ.get("DATABASE_URL")

# Same preference order as migration 0025.
_PRIORITY = [
    "trade_date",
    "date_publish",
    "publish_date",
    "date_published",
    "snapshot_date",
    "date_price_settlement",
    "date_trade",
    "date_delivery",
    "date_end",
    "start_date",
    "end_date",
    "last_trade_date",
    "report_date",
    "financial_date",
    "pub_date",
    "fetched_at",
    "created_at",
    "updated_at",
    "date",
]

_TIME_TYPES = {"time without time zone", "time with time zone"}


async def main() -> None:
    engine = create_async_engine(DB_URL)
    try:
        async with engine.begin() as conn:
            # tables that have the dual columns but no source entry
            missing = (
                await conn.execute(
                    text(
                        "SELECT c.table_name "
                        "FROM information_schema.columns c "
                        "WHERE c.table_schema = 'public' "
                        "  AND c.column_name = 'gregorian_date' "
                        "  AND c.table_name NOT LIKE 'alembic_%' "
                        "  AND c.table_name NOT IN (SELECT table_name FROM dual_date_columns) "
                        "GROUP BY c.table_name ORDER BY c.table_name"
                    )
                )
            ).scalars().all()

            fixed, no_source = [], []
            for table in missing:
                cols = {
                    r[0]: r[1]
                    for r in (
                        await conn.execute(
                            text(
                                "SELECT column_name, data_type FROM information_schema.columns "
                                "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position"
                            ),
                            {"t": table},
                        )
                    ).fetchall()
                }
                src = await _pick_source(conn, table, cols)
                if src is None:
                    no_source.append(table)
                    continue
                await conn.execute(
                    text("INSERT INTO dual_date_columns (table_name, source_column) VALUES (:t, :s)"),
                    {"t": table, "s": src},
                )
                await conn.execute(
                    text(
                        f'CREATE TRIGGER trg_dual_dates BEFORE INSERT OR UPDATE ON "{table}" '
                        f"FOR EACH ROW EXECUTE FUNCTION sync_dual_dates_fn()"
                    )
                )
                fixed.append((table, src))

        print(f"fixed with source+trigger ({len(fixed)}):")
        for t, s in fixed:
            print(f"  {t} -> {s}")
        print(f"no date source, left as-is ({len(no_source)}): {sorted(no_source)}")
    finally:
        await engine.dispose()


async def _has_data(conn, table: str, col: str) -> bool:
    return (
        (await conn.execute(text(f'SELECT 1 FROM "{table}" WHERE "{col}" IS NOT NULL LIMIT 1'))).first()
        is not None
    )


async def _pick_source(conn, table: str, cols: dict[str, str]) -> str | None:
    """Broadened version of migration 0025's picker (adds *_at / time / timestamp)."""
    names = {c for c in cols if c not in ("gregorian_date", "shamsi_date")}
    usable = [c for c in names if cols.get(c) not in _TIME_TYPES]

    for name in _PRIORITY:
        if name in usable and await _has_data(conn, table, name):
            return name
    for name in _PRIORITY:
        if name in usable:
            return name
    for name in sorted(usable):
        if (name == "date" or name.endswith("_date")) and await _has_data(conn, table, name):
            return name
    for name in sorted(usable):
        if name == "date" or name.endswith("_date"):
            return name
    # NEW: *_at columns (checked_at, triggered_at, last_trained_at, ...)
    for name in sorted(usable):
        if name.endswith("_at") and await _has_data(conn, table, name):
            return name
    for name in sorted(usable):
        if name.endswith("_at"):
            return name
    # NEW: generic time/timestamp columns
    for name in sorted(usable):
        if name in ("time", "timestamp") and await _has_data(conn, table, name):
            return name
    for name in sorted(usable):
        if name in ("time", "timestamp"):
            return name
    return None


if __name__ == "__main__":
    asyncio.run(main())
