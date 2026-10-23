"""Step 1 probe - shape of brsapi_historical_daily for the pinned symbols.

Read-only, indexed/bounded queries. Answers: how many rows share one
(symbol, gregorian_date), and how many distinct dates exist in the window
SignalBacktestEngine fetches (LIMIT days_forward ordered by date).
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import asyncio


def load_env() -> str:
    for line in Path(".env").read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    return os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)


async def main() -> None:
    eng = create_async_engine(load_env(), future=True)
    async with eng.connect() as c:
        dmax = (await c.execute(text("SELECT max(gregorian_date) FROM brsapi_historical_daily"))).fetchone()[0]
        print("max(gregorian_date) =", dmax)

        syms = (await c.execute(text(
            "SELECT DISTINCT symbol FROM brsapi_historical_daily "
            "WHERE gregorian_date = :d AND price_close > 0 ORDER BY symbol LIMIT 5"
        ), {"d": dmax})).fetchall()
        picked = [s[0] for s in syms]
        print("distinct symbols on max date (limit 5):", picked)

        n_syms = (await c.execute(text(
            "SELECT count(DISTINCT symbol) FROM brsapi_historical_daily WHERE gregorian_date = :d"
        ), {"d": dmax})).fetchone()[0]
        print("distinct symbols on max date =", n_syms)

        for sym in picked:
            r = (await c.execute(text(
                "SELECT count(*) AS rows, count(DISTINCT gregorian_date) AS days, "
                "max(gregorian_date) - min(gregorian_date) AS span_days "
                "FROM (SELECT gregorian_date FROM brsapi_historical_daily "
                "      WHERE symbol = :s ORDER BY gregorian_date DESC LIMIT 400) t"
            ), {"s": sym})).fetchone()
            print(f"  {sym!r}: last 400 rows cover {r[1]} distinct dates over {r[2]} calendar days")
            per_day = (await c.execute(text(
                "SELECT gregorian_date, count(*) FROM brsapi_historical_daily "
                "WHERE symbol = :s AND gregorian_date > :d2 "
                "GROUP BY gregorian_date ORDER BY gregorian_date DESC LIMIT 5"
            ), {"s": sym, "d2": date(2026, 9, 25)})).fetchall()
            print(f"    rows per date (latest): {[(str(x[0]), x[1]) for x in per_day]}")
    await eng.dispose()


asyncio.run(main())
