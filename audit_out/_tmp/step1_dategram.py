"""Step 1 probe - what does gregorian_date actually hold?

The backtest engine orders/filters on gregorian_date. If gregorian_date is the
sync/ingest date rather than the bar's trading date, the "future window" is not
a time series. Read-only, bounded by symbol index.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


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
        rows = (await c.execute(text(
            "SELECT id, date, gregorian_date, price_first, price_close "
            "FROM brsapi_historical_daily WHERE symbol = :s "
            "ORDER BY id DESC LIMIT 40"
        ), {"s": "آبادا"})).fetchall()
        print("id | jalali date | gregorian_date | first | close   (last 40 by id, newest id first)")
        for r in rows:
            print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]}")

        agg = (await c.execute(text(
            "SELECT count(*) AS n, count(DISTINCT date) AS jalali, "
            "count(DISTINCT gregorian_date) AS greg, "
            "count(DISTINCT (date, gregorian_date)) AS pairs "
            "FROM (SELECT id, date, gregorian_date FROM brsapi_historical_daily "
            "      WHERE symbol = :s ORDER BY id DESC LIMIT 400) t"
        ), {"s": "آبادا"})).fetchone()
        print(f"last 400 rows: n={agg[0]} distinct_jalali_dates={agg[1]} "
              f"distinct_gregorian_dates={agg[2]} distinct_pairs={agg[3]}")

        pairs = (await c.execute(text(
            "SELECT date, min(gregorian_date), max(gregorian_date), count(*) "
            "FROM brsapi_historical_daily WHERE symbol = :s "
            "GROUP BY date ORDER BY date DESC LIMIT 12"
        ), {"s": "آبادا"})).fetchall()
        print("jalali date -> min/max gregorian_date, rows:")
        for p in pairs:
            print(f"   {p[0]} -> {p[1]} .. {p[2]}  ({p[3]} rows)")
    await eng.dispose()


asyncio.run(main())
