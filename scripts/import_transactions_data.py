"""Import D:\\transactions_data daily trade JSON files into PostgreSQL.

The folder layout is ``<symbol>/<jalali-date>.json`` and each file is a JSON
array of ``{row,time,volume,price,canceled}``. Target table:
``brsapi_intraday_trades`` (symbol,row,time,volume,price,canceled,trade_date,
shamsi_date,gregorian_date,created_at).

Safety:
  * dry-run by default (``--execute`` writes);
  * never deletes/updates existing rows;
  * idempotent per (symbol, shamsi_date, row): existing rows are detected by
    ``row`` and skipped, so a re-run after a partial failure is safe;
  * commits per symbol.

Usage:
  python scripts/import_transactions_data.py --dry-run
  python scripts/import_transactions_data.py --execute
  python scripts/import_transactions_data.py --execute --only آباد --only-file 1405-07-28
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import jdatetime
import psycopg2
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
BASE = Path(r"D:\transactions_data")
ENV_FILE = ROOT / "_audit_base" / ".env"
MANIFEST = ROOT / "audit_out" / "transactions_manifest.json"
PLAN = ROOT / "audit_out" / "transactions_import_plan.json"
CANONICAL = {"آسیا": "آسيا"}
COLUMNS = (
    "symbol",
    "row",
    "time",
    "volume",
    "price",
    "canceled",
    "trade_date",
    "created_at",
    "gregorian_date",
    "shamsi_date",
)


def _dsn() -> str:
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    dsn = env.get("DATABASE_URL")
    if not dsn:
        raise SystemExit(f"DATABASE_URL not found in {ENV_FILE}")
    return re.sub(r"^postgresql\+[a-z0-9]+://", "postgresql://", dsn)


def _connect():
    parsed = urlparse(_dsn())
    return psycopg2.connect(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 5432,
        dbname=(parsed.path or "/").lstrip("/"),
        user=parsed.username,
        password=unquote(parsed.password or ""),
        connect_timeout=10,
        application_name="transactions_data_import",
    )


def _gregorian(shamsi: str):
    try:
        year, month, day = (int(part) for part in shamsi.split("-")[:3])
        return jdatetime.date(year, month, day).togregorian()
    except Exception:
        return None


def _row_tuple(symbol: str, shamsi: str, row: dict):
    return (
        symbol,
        int(row.get("row") or 0),
        str(row.get("time") or ""),
        int(row.get("volume") or 0),
        float(row.get("price") or 0.0),
        bool(int(row.get("canceled") or 0)),
        shamsi,
        dt.datetime.now(),
        _gregorian(shamsi),
        shamsi,
    )


def _existing_rows(cur, symbol: str, shamsi: str) -> set[int]:
    # (symbol, shamsi_date, row) is indexed; this is fast and exact even when
    # trade_date uses the Gregorian format for older rows.
    cur.execute(
        "select row from brsapi_intraday_trades where symbol=%s and shamsi_date=%s",
        (symbol, shamsi),
    )
    return {int(r[0]) for r in cur.fetchall() if r[0] is not None}


def _import_file(
    cur,
    folder: str,
    symbol: str,
    shamsi: str,
    db_count: int,
    db_max_row: int,
    refresh_state: bool = False,
) -> int:
    if refresh_state:
        cur.execute(
            "select count(*), max(row) from brsapi_intraday_trades "
            "where symbol=%s and shamsi_date=%s",
            (symbol, shamsi),
        )
        db_count, db_max_row = cur.fetchone()
        db_count = int(db_count or 0)
        db_max_row = int(db_max_row or 0)
    path = BASE / folder / f"{shamsi}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data:
        return 0
    if db_count == 0:
        selected = data
    elif db_count >= len(data):
        # DB already has at least every JSON row for this day; never delete or
        # update existing rows.
        return 0
    else:
        # Exact merge: insert only row numbers that are not present.
        existing = _existing_rows(cur, symbol, shamsi)
        selected = [row for row in data if int(row.get("row") or 0) not in existing]
    if not selected:
        return 0
    values = [_row_tuple(symbol, shamsi, row) for row in selected]
    execute_values(
        cur,
        f"INSERT INTO brsapi_intraday_trades ({','.join(COLUMNS)}) VALUES %s",
        values,
        page_size=5000,
    )
    return len(values)


def _normalise_nav(cur) -> int:
    """Copy the latest issue/redemption NAV per symbol-day into fund_nav_history."""
    cur.execute(
        """
        INSERT INTO fund_nav_history (
            fund_id, nav_date, nav_date_greg, nav_issue, nav_redemption,
            data_source, payload_version, created_at, updated_at
        )
        SELECT
            'tse:' || symbol,
            gregorian_date,
            gregorian_date,
            nav_issue,
            nav_redemption,
            'brsapi_nav_records',
            1,
            now(),
            now()
        FROM (
            SELECT DISTINCT ON (symbol, gregorian_date)
                symbol, gregorian_date, nav_issue, nav_redemption, time
            FROM brsapi_nav_records
            WHERE gregorian_date IS NOT NULL
            ORDER BY symbol, gregorian_date, time DESC NULLS LAST
        ) latest
        ON CONFLICT (fund_id, nav_date) DO NOTHING
        """
    )
    return cur.rowcount


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--only", action="append", default=[], help="symbol filter")
    parser.add_argument("--exclude", action="append", default=[], help="symbols already imported")
    parser.add_argument("--only-file", action="append", default=[], help="Jalali date filter")
    parser.add_argument("--skip-nav", action="store_true")
    parser.add_argument(
        "--refresh-state",
        action="store_true",
        help="query current (symbol, shamsi_date) counts instead of the stale plan",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="with --execute: run the inserts then roll the transaction back (safe test)",
    )
    args = parser.parse_args()

    if not MANIFEST.exists() or not PLAN.exists():
        raise SystemExit("manifest/plan missing; run the planning step first")

    # Manifest is validated for presence; the compact plan is what we execute.
    json.loads(MANIFEST.read_text(encoding="utf-8"))
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    only = {s.strip() for s in args.only}
    exclude = {s.strip() for s in args.exclude}
    only_file = {s.strip() for s in args.only_file}

    conn = _connect()
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("set statement_timeout='120s'")
    try:
        total_files = total_rows = 0
        for item in plan:
            symbol, folder = item["symbol"], item["folder"]
            if only and symbol not in only:
                continue
            if symbol in exclude:
                continue
            symbol_rows = 0
            files = item["files"]
            for shamsi, _add, _json_count, db_count, db_max_row in files:
                if only_file and shamsi not in only_file:
                    continue
                if args.execute:
                    got = _import_file(
                        cur,
                        folder,
                        symbol,
                        shamsi,
                        int(db_count),
                        int(db_max_row),
                        refresh_state=args.refresh_state,
                    )
                else:
                    got = int(_add)
                if got:
                    total_files += 1
                    total_rows += got
                    symbol_rows += got
            if args.execute and symbol_rows and not args.rollback:
                conn.commit()
                print(
                    f"{symbol}: +{symbol_rows:,} rows committed", flush=True
                )
        if args.execute and not args.skip_nav and not only and not only_file:
            nav = _normalise_nav(cur)
            if args.rollback:
                print(f"fund_nav_history: would add {nav:,} rows (rolled back)", flush=True)
            else:
                conn.commit()
                print(f"fund_nav_history: +{nav:,} rows", flush=True)
        if args.execute and args.rollback:
            conn.rollback()
            print("ROLLED BACK — no rows persisted", flush=True)
        print(
            f"{'WROTE' if args.execute else 'DRY-RUN'}: "
            f"files={total_files:,} rows={total_rows:,}",
            flush=True,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
