"""Step 1 - build an isolated copy of the price bars used by SignalBacktestEngine.

Read-only against the live DB, bounded/indexed queries only (the live table is ~10 GB).
Writes ONLY to audit_out/_tmp/step1_copy.sqlite and _tmp/step1_pinned_signals.json.
No credentials are printed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TMP = Path("audit_out/_tmp")
COPY = TMP / "step1_copy.sqlite"
N_SYMBOLS = 5
BARS_PER_SYMBOL = 400


def load_env() -> str:
    for line in Path(".env").read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    return os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)


async def main() -> None:
    url = load_env()
    eng = create_async_engine(url, future=True)
    async with eng.connect() as c:
        t0 = time.monotonic()
        dmax = (await c.execute(text(
            "SELECT max(gregorian_date) FROM brsapi_historical_daily"
        ))).fetchone()[0]
        print(f"LIVE max(gregorian_date) = {dmax}  ({time.monotonic() - t0:.2f}s)")

        rows = (await c.execute(text(
            "SELECT symbol, price_close FROM brsapi_historical_daily "
            "WHERE gregorian_date = :d AND price_close > 0 "
            "ORDER BY symbol LIMIT :k"
        ), {"d": dmax, "k": N_SYMBOLS})).fetchall()
        picked = [r[0] for r in rows]
        print("picked symbols:", picked)

        bars: list[tuple] = []
        for sym in picked:
            t1 = time.monotonic()
            r = (await c.execute(text(
                "SELECT symbol, gregorian_date, price_first, price_max, price_min, price_close "
                "FROM brsapi_historical_daily WHERE symbol = :s AND price_close > 0 "
                "ORDER BY gregorian_date DESC LIMIT :k"
            ), {"s": sym, "k": BARS_PER_SYMBOL})).fetchall()
            bars.extend(r)
            print(f"  {sym}: fetched {len(r)} bars ({time.monotonic() - t1:.2f}s)")
    await eng.dispose()

    if COPY.exists():
        COPY.unlink()
    con = sqlite3.connect(COPY)
    con.execute(
        "CREATE TABLE brsapi_historical_daily ("
        "symbol TEXT, gregorian_date TEXT, price_first REAL, price_max REAL, "
        "price_min REAL, price_close REAL)"
    )
    con.executemany(
        "INSERT INTO brsapi_historical_daily VALUES (?,?,?,?,?,?)",
        [(r[0], str(r[1]), r[2], r[3], r[4], r[5]) for r in bars],
    )
    con.commit()
    per = con.execute(
        "SELECT symbol, count(*), min(gregorian_date), max(gregorian_date) "
        "FROM brsapi_historical_daily GROUP BY symbol ORDER BY symbol"
    ).fetchall()
    total = con.execute("SELECT count(*) FROM brsapi_historical_daily").fetchone()[0]
    print(f"COPY {COPY}: rows={total}")
    for p in per:
        print(f"  {p[0]}: n={p[1]} {p[2]}..{p[3]}")

    # pinned, reproducible input signals derived from the copy (oldest bar of each series)
    pinned = []
    for i, (sym, _cnt, _dmin, _dmax) in enumerate(per, start=1):
        first = con.execute(
            "SELECT gregorian_date, price_first, price_close FROM brsapi_historical_daily "
            "WHERE symbol=? ORDER BY gregorian_date ASC LIMIT 1", (sym,)
        ).fetchone()
        pinned.append({
            "signal_id": f"step1-{i:03d}",
            "symbol": sym,
            "market": "stock",
            "direction": "buy",
            "timeframe": "daily",
            "date": str(first[0]),
            "price": float(first[1] or first[2]),
            "source": "rule_based",
            "targets": "",
            "stop_loss": "",
        })
    con.close()
    (TMP / "step1_pinned_signals.json").write_text(json.dumps(pinned, indent=2), encoding="utf-8")
    print(f"wrote {TMP / 'step1_pinned_signals.json'} with {len(pinned)} pinned signals")


asyncio.run(main())
