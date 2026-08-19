"""
Sync Delta Report - compare table rows/freshness before vs after a sync
========================================================================

Captures a snapshot of the key BrsApi tables (row count, distinct symbols,
max created_at, max gregorian_date) into a JSON file, then - after a sync
run - captures again and prints the DELTA: how many rows/symbols were added
and how freshness moved.

Usage:
    # 1. Capture the "before" baseline (overwrites json/brsapi/sync_baseline.json)
    python scripts/sync_delta_report.py --before

    # 2. Run your sync (e.g. python scripts/run_backlog_sync.py) ...

    # 3. Capture "after" and print the delta table
    python scripts/sync_delta_report.py

    # Markdown output (e.g. for the docs/report)
    python scripts/sync_delta_report.py --format markdown

    # Override baseline path
    python scripts/sync_delta_report.py --before --baseline /tmp/baseline.json
    python scripts/sync_delta_report.py --baseline /tmp/baseline.json

Exit code: 0 = comparison succeeded (delta shown in output), 2 = baseline
missing (capture --before first). The delta size is reported in the output,
not the exit code, so this is safe to chain with &&.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

DEFAULT_BASELINE = Path(_project_root) / "json" / "brsapi" / "sync_baseline.json"

# (table, symbol_col, ts_col, date_col)
TABLES: list[tuple[str, str, str, str]] = [
    ("brsapi_symbol_snapshots", "symbol", "created_at", "gregorian_date"),
    ("brsapi_symbol_details", "symbol", "fetched_at", "gregorian_date"),
    ("brsapi_candlesticks", "symbol", "created_at", "gregorian_date"),
    ("brsapi_historical_daily", "symbol", "created_at", "gregorian_date"),
    ("brsapi_historical_real_legal", "symbol", "created_at", "gregorian_date"),
    ("brsapi_shareholder_records", "symbol", "created_at", "gregorian_date"),
    ("brsapi_index_values", "name", "created_at", "gregorian_date"),
    ("brsapi_intraday_trades", "symbol", "created_at", "gregorian_date"),
    ("brsapi_option_snapshots", "symbol", "created_at", "gregorian_date"),
    ("screener_daily_scores", "symbol", "calculated_at", "trade_date"),
    ("ml_engineered_features", "symbol", "calculated_at", "trade_date"),
]


async def capture(fast: bool = False) -> dict[str, Any]:
    """Return a snapshot dict of all tracked tables.

    ``fast=True`` reads ``n_live_tup`` from ``pg_stat_user_tables`` instead
    of running any real query — near-instant. NOTE: these are optimizer
    estimates only; they can be badly stale (autovacuum/ANALYZE dependent)
    and ``max_ts``/``max_date`` are not collected, so fast mode is only good
    for a rough before/after sanity check. Use exact mode (default) for
    accurate verification.
    """
    from sqlalchemy import text

    from core.database import get_session

    snapshot: dict[str, Any] = {"captured_at": datetime.now(UTC).isoformat(), "tables": {}}
    async for session in get_session():
        for table, sym_col, ts_col, date_col in TABLES:
            entry: dict[str, Any] = {"rows": 0, "symbols": 0, "max_ts": None, "max_date": None}
            try:
                if fast:
                    r = await session.execute(
                        text(
                            "SELECT n_live_tup FROM pg_stat_user_tables "
                            "WHERE relname = :t"
                        ),
                        {"t": table},
                    )
                    row = r.fetchone()
                    if row is not None and row[0] is not None:
                        entry["rows"] = int(row[0])
                        # Approximate only — no per-column distinct estimate
                        # here, and timestamps are skipped entirely for speed.
                        entry["symbols"] = int(row[0])
                        entry["fast_estimate"] = True
                    else:
                        entry["error"] = "table not in pg_stat_user_tables"
                else:
                    r = await session.execute(
                        text(f"SELECT count(*), count(DISTINCT {sym_col}) FROM {table}")
                    )
                    entry["rows"], entry["symbols"] = (int(v) for v in r.fetchone())
                    r = await session.execute(text(f"SELECT max({ts_col}) FROM {table}"))
                    val = r.scalar()
                    entry["max_ts"] = str(val) if val is not None else None
                    r = await session.execute(text(f"SELECT max({date_col}) FROM {table}"))
                    val = r.scalar()
                    entry["max_date"] = str(val) if val is not None else None
            except Exception as exc:  # noqa: BLE001
                entry["error"] = str(exc)[:80]
            snapshot["tables"][table] = entry
        break
    return snapshot


def _write_before(snapshot: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _diff(after: dict[str, Any], before: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute the per-table delta between two snapshots."""
    rows: list[dict[str, Any]] = []
    for table, _, _, _ in TABLES:
        b = before.get("tables", {}).get(table, {})
        a = after.get("tables", {}).get(table, {})
        if "error" in a or "error" in b:
            rows.append({
                "table": table, "rows_before": None, "rows_after": None,
                "rows_delta": None, "symbols_before": None, "symbols_after": None,
                "symbols_delta": None, "ts_before": b.get("max_ts"), "ts_after": a.get("max_ts"),
                "date_before": b.get("max_date"), "date_after": a.get("max_date"),
            })
            continue
        rows.append({
            "table": table,
            "rows_before": b.get("rows", 0), "rows_after": a.get("rows", 0),
            "rows_delta": (a.get("rows", 0) or 0) - (b.get("rows", 0) or 0),
            "symbols_before": b.get("symbols", 0), "symbols_after": a.get("symbols", 0),
            "symbols_delta": (a.get("symbols", 0) or 0) - (b.get("symbols", 0) or 0),
            "ts_before": b.get("max_ts"), "ts_after": a.get("max_ts"),
            "date_before": b.get("max_date"), "date_after": a.get("max_date"),
        })
    return rows


def _p(msg: str) -> None:
    """Windows cp1252-safe print (Persian text otherwise crashes the console)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def _print_plain(rows: list[dict[str, Any]], before_ts: str, after_ts: str) -> None:
    _p(f"BEFORE (captured {before_ts}):")
    _p(f"AFTER  (captured {after_ts}):")
    _p("")
    header = f"{'TABLE':<30} {'ROWS':>11} {'+NEW':>9} {'SYMS':>7} {'+SYMS':>7}  {'MAX_DATE'}"
    _p(header)
    _p("-" * len(header))
    for r in rows:
        if r["rows_before"] is None:
            _p(f"{r['table']:<30} ERROR (see snapshot json)")
            continue
        _p(
            f"{r['table']:<30} {r['rows_after']:>11,} {r['rows_delta']:>+9,} "
            f"{r['symbols_after']:>7,} {r['symbols_delta']:>+7,}  {r['date_after']}"
        )
    total_new = sum(r["rows_delta"] or 0 for r in rows)
    _p("-" * len(header))
    _p(f"{'TOTAL NEW ROWS':<30} {total_new:>11,}")


def _print_markdown(rows: list[dict[str, Any]], before_ts: str, after_ts: str) -> None:
    _p(f"> BEFORE: {before_ts}")
    _p(f"> AFTER:  {after_ts}")
    _p("")
    _p("| Table | Rows before | Rows after | New rows | Symbols before | Symbols after | New symbols | Max date |")
    _p("|---|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        if r["rows_before"] is None:
            _p(f"| {r['table']} | ERROR | | | | | | |")
            continue
        _p(
            f"| {r['table']} | {r['rows_before']:,} | {r['rows_after']:,} | "
            f"{r['rows_delta']:+,} | {r['symbols_before']:,} | {r['symbols_after']:,} | "
            f"{r['symbols_delta']:+,} | {r['date_after']} |"
        )
    total_new = sum(r["rows_delta"] or 0 for r in rows)
    _p(f"| **TOTAL NEW ROWS** | | | **{total_new:,}** | | | | |")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", action="store_true",
                        help="Capture the baseline snapshot (before sync)")
    parser.add_argument("--baseline", type=str, default=None,
                        help=f"Baseline JSON path (default: {DEFAULT_BASELINE})")
    parser.add_argument("--format", choices=["plain", "markdown"], default="plain")
    parser.add_argument("--fast", action="store_true",
                        help="Use approximate pg_stat_user_tables counts (near-instant, estimates)")
    args = parser.parse_args(argv)

    path = Path(args.baseline) if args.baseline else DEFAULT_BASELINE

    if args.before:
        snap = asyncio.run(capture(fast=args.fast))
        _write_before(snap, path)
        _p(f"Baseline captured -> {path}")
        _p(f"  tables: {len(snap['tables'])} | captured_at: {snap['captured_at']} | fast={args.fast}")
        return 0

    if not path.exists():
        _p(f"Baseline not found: {path}")
        _p("Run `python scripts/sync_delta_report.py --before` first.")
        return 2

    before = json.loads(path.read_text(encoding="utf-8"))
    after = asyncio.run(capture(fast=args.fast))
    rows = _diff(after, before)

    if args.format == "markdown":
        _print_markdown(rows, before["captured_at"], after["captured_at"])
    else:
        _print_plain(rows, before["captured_at"], after["captured_at"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
