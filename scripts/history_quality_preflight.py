"""Read-only pre-flight for the gold/coin/FX/NAV history findings (stage 7).

The stage-7 audit had to stop at "needs the operational database". This script is
the missing piece: it runs the data-quality checks **without writing anything**,
so the owner can produce the numbers that were reported as BLOCKED.

Safety
------
* Every statement executed by :func:`all_statements` is a ``SELECT``. Nothing in
  this file issues ``INSERT``/``UPDATE``/``DELETE``/``TRUNCATE``/``ALTER``/
  ``DROP``/``CREATE``. The remediation DDL in :data:`REVIEW_ONLY_DDL` is only
  printed for review — it is never executed.
* ``statement_timeout`` is set from ``--timeout-ms`` (default 120s).
* The DSN / credentials are never printed; a failure shows only the exception
  class and message.
* Nothing is cached or written except the optional ``--json`` output file.

Usage
-----
    python scripts/history_quality_preflight.py
    python scripts/history_quality_preflight.py --timeout-ms 60000 --json /tmp/quality.json

What it answers
---------------
1. The OHLC/NAV checks from ``brsapi.quality.history_quality_queries``
   (high<low, close/open outside range, non-positive, duplicates, unparsable
   and slash-separated dates, trading-date span).
2. Column types of the time columns — in particular whether ``fetched_at`` is
   text (writable by the ingestion fix) or a timestamp.
3. ``dual_date_columns.source_column`` for each table: migration 0025 fills
   ``gregorian_date``/``shamsi_date`` from that source, and for these tables it
   picked ``fetched_at``/``created_at`` (ingestion time), not ``date``.
4. Existing indexes, to see whether ``ON CONFLICT (symbol, date)`` has a unique
   index behind it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from brsapi.quality import (  # noqa: E402
    NAV_HISTORY_TABLES,
    OHLC_HISTORY_TABLES,
    history_quality_queries,
)

TABLES: tuple[str, ...] = OHLC_HISTORY_TABLES + NAV_HISTORY_TABLES

# Columns whose meaning the stage-7 report had to pin down.
TIME_COLUMNS: tuple[str, ...] = (
    "date",
    "fetched_at",
    "created_at",
    "updated_at",
    "gregorian_date",
    "shamsi_date",
)

# Printed for review only. Applying these is an owner decision (they need a
# maintenance window and a duplicate check on a live table), so they are never
# executed by this script.
REVIEW_ONLY_DDL: tuple[str, ...] = tuple(
    f"-- {table}: review duplicates first, then (maintenance window):\n"
    f"-- CREATE UNIQUE INDEX CONCURRENTLY uq_{table}_symbol_date"
    f" ON {table} (symbol, date);"
    for table in OHLC_HISTORY_TABLES
) + (
    "-- After the index exists, ON CONFLICT (symbol, date) in "
    "brsapi/services/history_fetch_service.py becomes valid.\n"
    "-- Re-check duplicates: the script above prints them under "
    "'duplicate_symbol_date'.",
    "-- dual-date mapping (migration 0025 picked an ingestion column):\n"
    "-- UPDATE dual_date_columns SET source_column = 'date'\n"
    "--  WHERE table_name IN ('brsapi_gold_coin_history',\n"
    "--        'brsapi_gold_currency_pro_daily_history', 'brsapi_nav_records');\n"
    "-- then refresh connections (the trigger caches the source per session) and\n"
    "-- run: python scripts/backfill_dual_dates.py",
)


def _table_list_sql() -> str:
    return ", ".join(f"'{table}'" for table in TABLES)


def all_statements() -> list[tuple[str, str]]:
    """Every statement this script may execute: ``[(label, sql), ...]``.

    All entries are single ``SELECT`` statements, so a reviewer can diff this
    list and know nothing will be written.
    """
    statements: list[tuple[str, str]] = []

    for table in TABLES:
        for check, sql in history_quality_queries(table).items():
            statements.append((f"{table}.{check}", sql))

    columns = ", ".join(f"'{column}'" for column in TIME_COLUMNS)
    statements.append(
        (
            "schema.time_columns",
            "SELECT table_name, column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            f"AND table_name IN ({_table_list_sql()}) "
            f"AND column_name IN ({columns}) "
            "ORDER BY table_name, column_name",
        )
    )
    statements.append(
        (
            "schema.dual_date_source",
            "SELECT table_name, source_column FROM dual_date_columns "
            f"WHERE table_name IN ({_table_list_sql()}) ORDER BY table_name",
        )
    )
    statements.append(
        (
            "schema.indexes",
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' "
            f"AND tablename IN ({_table_list_sql()}) "
            "ORDER BY tablename, indexname",
        )
    )
    return statements


def _rows_to_json(result: Any) -> list[dict[str, Any]]:
    """AsyncResult rows → JSON-safe dicts (dates/Decimals stringified)."""
    rows: list[dict[str, Any]] = []
    keys = list(result.keys()) if hasattr(result, "keys") else []
    for row in result.fetchall() if hasattr(result, "fetchall") else result:
        mapping = row._mapping if hasattr(row, "_mapping") else None
        if mapping is not None:
            item = {key: _jsonable(mapping[key]) for key in keys or mapping.keys()}
        elif isinstance(row, (tuple, list)):
            item = {str(i): _jsonable(value) for i, value in enumerate(row)}
        else:
            item = {"value": _jsonable(row)}
        rows.append(item)
    return rows


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


async def run(timeout_ms: int = 120_000) -> dict[str, Any]:
    """Execute every read-only statement and return a serialisable report."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from core.config import settings

    url = getattr(settings, "database_url_async", None) or settings.database_url
    engine = create_async_engine(url)
    report: dict[str, Any] = {"tables": list(TABLES), "timeout_ms": timeout_ms, "checks": {}}
    try:
        async with engine.connect() as conn:
            # Session-level guard: no statement can run away on a big table.
            await conn.execute(text(f"SET statement_timeout = {int(timeout_ms)}"))
            for label, sql in all_statements():
                assert sql.lstrip().upper().startswith("SELECT"), label
                try:
                    result = await conn.execute(text(sql))
                    report["checks"][label] = {"rows": _rows_to_json(result)}
                except Exception as exc:  # noqa: BLE001 — one bad probe must not stop the rest
                    report["checks"][label] = {
                        "error": f"{type(exc).__name__}: {exc}"[:300],
                    }
    finally:
        await engine.dispose()

    report["review_only_ddl"] = list(REVIEW_ONLY_DDL)
    report["note"] = (
        "Read-only. No INSERT/UPDATE/DELETE was issued. review_only_ddl is "
        "printed for review and was not executed."
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only history data-quality pre-flight")
    parser.add_argument("--timeout-ms", type=int, default=120_000, help="statement_timeout per query")
    parser.add_argument("--json", type=Path, default=None, help="optional output file")
    args = parser.parse_args(argv)

    report = asyncio.run(run(timeout_ms=args.timeout_ms))
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
