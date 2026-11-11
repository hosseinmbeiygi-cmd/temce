#!/usr/bin/env python3
"""Fetch intraday trades (ریز معاملات) for symbols that are missing a given
trading day, then store them the same way the crawler does.

Only symbols with **no** rows for the target date are requested, so this can
never create duplicate rows. Results are written to
``transactions_data/<symbol>/<date>.json`` (the crawler cache) and inserted
into ``brsapi_intraday_trades`` via z.py's dedupe path.

Usage:
    python scripts/fetch_missing_trades.py --dry-run
    python scripts/fetch_missing_trades.py                     # last trading day in PG
    python scripts/fetch_missing_trades.py --date 1405-07-15
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import psycopg2  # noqa: E402
import requests  # noqa: E402

import z  # noqa: E402

_JALALI_RE = r"^1[34][0-9]{2}-[0-9]{2}-[0-9]{2}$"


def pg_dates_and_symbols(cur, target: str | None):
    """Return (target_date, candidates) where candidates are the symbols that
    traded on the most recent date before ``target``."""
    if target is None:
        cur.execute(
            "SELECT max(trade_date) FROM " + z.TRADES_TABLE + " WHERE trade_date ~ %s",
            (_JALALI_RE,),
        )
        target = cur.fetchone()[0]
    cur.execute(
        "SELECT max(trade_date) FROM " + z.TRADES_TABLE +
        " WHERE trade_date ~ %s AND trade_date < %s",
        (_JALALI_RE, target),
    )
    ref = cur.fetchone()[0]
    if not ref:
        return target, []
    cur.execute(
        "SELECT DISTINCT symbol FROM " + z.TRADES_TABLE + " WHERE trade_date = %s",
        (ref,),
    )
    candidates = sorted({r[0] for r in cur.fetchall() if r[0]})
    return target, candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=None, help="Jalali date (default: max in Postgres)")
    parser.add_argument("--symbols", default=None, help="Comma-separated whitelist")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = psycopg2.connect(**z.PG_CONFIG)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            target, candidates = pg_dates_and_symbols(cur, args.date)
            if not target:
                print("No Jalali trade_date in Postgres yet — nothing to do.")
                return 0
            if args.symbols:
                wanted = {s.strip() for s in args.symbols.split(",") if s.strip()}
                candidates = [s for s in candidates if s in wanted]

            cur.execute(
                "SELECT DISTINCT symbol FROM " + z.TRADES_TABLE + " WHERE trade_date = %s",
                (target,),
            )
            have = {r[0] for r in cur.fetchall()}
            missing = [s for s in candidates if s not in have]

            print(f"target date            : {target}")
            print(f"candidate symbols      : {len(candidates)}")
            print(f"already have {target}: {len(have)}")
            print(f"missing                : {len(missing)} -> {missing}")
            if args.dry_run:
                print("[DRY-RUN] no requests sent.")
                return 0
            if not missing:
                print("nothing to fetch.")
                return 0

            ins_map = z._load_ins_id_map(cur)
            url = f"{z.BASE_URL}/Tsetmc/Transaction.php"
            data_dir = Path(z.DATA_DIR)

            total_new = total_dup = 0
            for i, symbol in enumerate(missing, 1):
                try:
                    resp = requests.get(
                        url,
                        params={"key": z.API_KEY, "l18": symbol, "date": target},
                        headers=z.HEADERS,
                        timeout=20,
                    )
                    if resp.status_code != 200:
                        print(f"  [{i}/{len(missing)}] {symbol}: HTTP {resp.status_code}")
                        time.sleep(args.delay)
                        continue
                    payload = resp.json()
                except Exception as exc:  # noqa: BLE001
                    print(f"  [{i}/{len(missing)}] {symbol}: request failed ({exc})")
                    time.sleep(args.delay)
                    continue

                rows = z._extract_trade_rows(payload)
                # Always refresh the crawler cache so z.py's resume logic sees
                # this (symbol, date) as done.
                out = data_dir / symbol / f"{target}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                raw = payload if isinstance(payload, list) else rows
                with open(out, "w", encoding="utf-8") as fh:
                    json.dump(raw, fh, ensure_ascii=False)

                if not rows:
                    print(f"  [{i}/{len(missing)}] {symbol}: 0 ticks")
                else:
                    batch = [
                        (symbol, target, r["seq_no"], r["time"], r["volume"],
                         r["price"], r["is_canceled"])
                        for r in rows
                    ]
                    ins, dup = z._insert_batch_no_dup(cur, batch, ins_map)
                    total_new += ins
                    total_dup += dup
                    print(f"  [{i}/{len(missing)}] {symbol}: {ins:,} inserted "
                          f"({dup} dup skipped)")
                time.sleep(args.delay)

            print(f"\nDone: inserted {total_new:,} rows, skipped {total_dup:,} duplicates.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
