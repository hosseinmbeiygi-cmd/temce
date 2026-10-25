#!/usr/bin/env python3
"""Import cached ``transactions_data/<symbol>/<jalali-date>.json`` files into
``brsapi_intraday_trades`` — no BrsApi requests are made.

The crawler (``z.py``) already stores every Transaction.php response on disk.
When the table lags behind those files, this fills the gap for free by reusing
z.py's own insert path, so the dedupe rule is identical to the live crawler
(key: ``symbol`` + ``trade_date`` + ``row``) and re-running never inserts
duplicate rows.

Usage:
    python scripts/import_cached_trades.py --dry-run
    python scripts/import_cached_trades.py                      # since last PG date
    python scripts/import_cached_trades.py --since 1405-07-13
    python scripts/import_cached_trades.py --since 1405-07-13 --symbols متال,طلا
    python scripts/import_cached_trades.py --since 1390-01-01 --until 1403-12-31

``--since``/``--until`` bound the (Jalali) dates to consider, so the same cache
can be imported by several parallel processes over disjoint symbol/date chunks
(each ``(symbol, trade_date)`` pair belongs to exactly one chunk, which keeps
the dedupe check race-free).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import psycopg2  # noqa: E402

import z  # noqa: E402  (crawler module: PG_CONFIG, TRADES_TABLE, dedupe helpers)

# Jalali trade dates look like 1405-07-15; a few legacy rows hold Gregorian
# dates ("2026-07-15") and would poison a plain string MAX().
_JALALI_RE = r"^1[34][0-9]{2}-[0-9]{2}-[0-9]{2}$"


def pg_max_trade_date(cur) -> str:
    cur.execute(
        "SELECT max(trade_date) FROM " + z.TRADES_TABLE + " WHERE trade_date ~ %s",
        (_JALALI_RE,),
    )
    return cur.fetchone()[0] or ""


def iter_cached_files(
    data_dir: Path, since: str, symbols: set[str] | None, *,
    exclusive: bool = False, until: str | None = None,
):
    """Yield ``(symbol, date, path)`` for cached files in the wanted range.

    ``exclusive`` skips dates <= since (used with the auto-detected Postgres
    max, which is already present); otherwise since is an inclusive lower bound.
    ``until`` is an inclusive upper bound (None = no upper bound).
    """
    if not data_dir.exists():
        return
    for sym_dir in sorted(data_dir.iterdir()):
        if not sym_dir.is_dir():
            continue
        if symbols and sym_dir.name not in symbols:
            continue
        for path in sorted(sym_dir.glob("*.json")):
            date = path.stem
            if since and (date <= since if exclusive else date < since):
                continue
            if until and date > until:
                continue
            yield sym_dir.name, date, path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since", default="auto",
        help="Import cached dates >= this Jalali date (default: auto = the "
             "current MAX(trade_date) in Postgres)",
    )
    parser.add_argument(
        "--until", default=None,
        help="Import cached dates <= this Jalali date (default: no upper bound)",
    )
    parser.add_argument("--data-dir", default=z.DATA_DIR)
    parser.add_argument("--symbols", default=None,
                        help="Comma-separated symbol whitelist (default: all)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    symbols = {s.strip() for s in args.symbols.split(",") if s.strip()} if args.symbols else None
    data_dir = Path(args.data_dir)

    conn = psycopg2.connect(**z.PG_CONFIG)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            auto = args.since == "auto"
            since = pg_max_trade_date(cur) if auto else args.since
            # ``since`` is the last date ALREADY present — only dates after it
            # are missing (string compare works: fixed-width Jalali dates).
            print(
                f"Postgres max trade_date = {since or '(empty)'}  -> importing "
                f"cached dates {'>' if auto else '>='} {since or 'any'}"
            )
            ins_map = z._load_ins_id_map(cur)
            print(f"ins_id map loaded for {len(ins_map)} symbols")

            total_files = total_in = total_skip = total_rows = 0
            per_date: dict[str, list[int]] = {}

            for symbol, date, path in iter_cached_files(
                data_dir, since, symbols, exclusive=auto, until=args.until
            ):
                total_files += 1
                try:
                    with open(path, encoding="utf-8") as fh:
                        payload = json.load(fh)
                except Exception as exc:  # noqa: BLE001
                    print(f"  [SKIP] {symbol}/{date}: unreadable JSON ({exc})")
                    continue

                rows = z._extract_trade_rows(payload)
                if not rows:
                    continue
                batch = [
                    (symbol, date, r["seq_no"], r["time"], r["volume"],
                     r["price"], r["is_canceled"])
                    for r in rows
                ]
                total_rows += len(batch)
                if args.dry_run:
                    stats = per_date.setdefault(date, [0, 0, 0])
                    stats[0] += 1
                    stats[1] += len(batch)
                    continue
                inserted, skipped = z._insert_batch_no_dup(cur, batch, ins_map)
                total_in += inserted
                total_skip += skipped
                stats = per_date.setdefault(date, [0, 0, 0])
                stats[0] += 1
                stats[1] += inserted
                stats[2] += skipped

            print()
            for date in sorted(per_date):
                files, ins, skip = per_date[date]
                print(f"  {date}: {files:>4} file(s)  inserted {ins:>8,}  "
                      f"skipped(dup) {skip:>8,}")
            print()
            if args.dry_run:
                print(f"[DRY-RUN] {total_files} file(s), {total_rows:,} rows would be considered.")
            else:
                print(f"Done: {total_files} file(s); inserted {total_in:,}; "
                      f"duplicates skipped {total_skip:,}.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
