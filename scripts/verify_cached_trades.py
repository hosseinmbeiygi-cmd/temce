# -*- coding: utf-8 -*-
"""Verify that every cached ``transactions_data/<symbol>/<date>.json`` file is
fully present in Postgres ``brsapi_intraday_trades``.

For each cached (symbol, date) pair the JSON's ``row`` (= ``seq_no``) values are
compared against the table's ``"row"`` values — that triple is the import dedupe
key, so a missing ``row`` means a row the crawler cached but Postgres lacks.

Usage:
    python scripts/verify_cached_trades.py --sample 50
    python scripts/verify_cached_trades.py                # every cached file

Exit status: 0 when nothing is missing, 1 when any row is missing from Postgres.
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

import z  # noqa: E402

DATE_BATCH = 40


def cached_files(data_dir: Path) -> dict[str, set[str]]:
    """{symbol: {date, ...}} for cached files that actually carry rows."""
    out: dict[str, set[str]] = {}
    for sym_dir in sorted(data_dir.iterdir()):
        if not sym_dir.is_dir():
            continue
        dates = {p.stem for p in sym_dir.glob("*.json")}
        if dates:
            out[sym_dir.name] = dates
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=z.DATA_DIR)
    ap.add_argument("--sample", type=int, default=0,
                    help="check only this many (symbol, date) pairs per symbol")
    args = ap.parse_args()

    files = cached_files(Path(args.data_dir))
    total_pairs = sum(len(d) for d in files.values())
    print(f"cached symbols={len(files)} pairs={total_pairs}", flush=True)

    conn = psycopg2.connect(**z.PG_CONFIG)
    conn.autocommit = True

    checked = json_rows = missing_rows = 0
    bad_pairs: list[tuple[str, str, int, int]] = []
    empty_pairs: list[tuple[str, str]] = []
    unreadable: list[tuple[str, str]] = []

    for symbol, dates in files.items():
        want = sorted(dates)
        if args.sample:
            want = want[: args.sample]
        for i in range(0, len(want), DATE_BATCH):
            chunk = want[i:i + DATE_BATCH]
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT trade_date, "row" FROM ' + z.TRADES_TABLE +
                    " WHERE symbol=%s AND trade_date = ANY(%s)",
                    (symbol, chunk),
                )
                db: dict[str, set[int]] = {}
                for d, rn in cur.fetchall():
                    db.setdefault(d, set()).add(rn)
            for date in chunk:
                path = Path(args.data_dir) / symbol / f"{date}.json"
                checked += 1
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    unreadable.append((symbol, date))
                    continue
                rows = z._extract_trade_rows(payload)
                if not rows:
                    empty_pairs.append((symbol, date))
                    continue
                src = {r["seq_no"] for r in rows}
                json_rows += len(src)
                absent = src - db.get(date, set())
                if absent:
                    missing_rows += len(absent)
                    bad_pairs.append((symbol, date, len(absent), len(src)))
                    if len(bad_pairs) <= 20:
                        print(f"  MISSING {symbol} {date}: {len(absent)}/{len(src)}",
                              flush=True)
        print(f"  {symbol}: checked -> pairs={checked} missing={missing_rows}",
              flush=True)

    print()
    print(f"checked pairs           : {checked}")
    print(f"json distinct rows      : {json_rows:,}")
    print(f"missing rows in PG      : {missing_rows:,}")
    print(f"pairs with missing rows : {len(bad_pairs)}")
    print(f"pairs with no json rows : {len(empty_pairs)}")
    print(f"unreadable json         : {len(unreadable)}")
    if bad_pairs:
        worst = sorted(bad_pairs, key=lambda x: -x[2])[:10]
        print("worst:", worst)
    conn.close()
    return 1 if missing_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
