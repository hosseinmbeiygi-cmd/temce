"""Step 1 probe - duplication inside brsapi_historical_daily for one (symbol, date).

Explains why the 30-row forward window of SignalBacktestEngine spans ~1 calendar day.
Read-only, bounded by the (symbol, gregorian_date) index. No credentials printed.
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
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
        for sym, d in [("آبادا", date(2026, 10, 8)), ("آ س پ", date(2026, 10, 8))]:
            r = (await c.execute(text(
                "SELECT count(*) AS n, count(DISTINCT price_close) AS px, "
                "count(DISTINCT ins_id) AS ins, count(DISTINCT date) AS jalali, "
                "min(id) AS id_min, max(id) AS id_max, min(price_close), max(price_close) "
                "FROM brsapi_historical_daily WHERE symbol = :s AND gregorian_date = :d"
            ), {"s": sym, "d": d})).fetchone()
            print(f"{sym!r} {d}: rows={r[0]} distinct_close={r[1]} distinct_ins_id={r[2]} "
                  f"distinct_jalali_date={r[3]} id={r[4]}..{r[5]} close={r[6]}..{r[7]}")

            rows = (await c.execute(text(
                "SELECT id, date, ins_id, instrument_id, price_first, price_close "
                "FROM brsapi_historical_daily WHERE symbol = :s AND gregorian_date = :d "
                "ORDER BY id LIMIT 12"
            ), {"s": sym, "d": d})).fetchall()
            for x in rows:
                print("   ", tuple(str(v) for v in x))

        # what the engine's exact query returns for a pinned anchor (LIMIT 30, gregorian_date > anchor)
        anchor = date(2026, 9, 16)
        rows = (await c.execute(text(
            "SELECT gregorian_date, symbol, price_first, price_close "
            "FROM brsapi_historical_daily "
            "WHERE symbol = :s AND price_close > 0 AND gregorian_date > :from_date "
            "ORDER BY gregorian_date ASC LIMIT :days"
        ), {"s": "آبادا", "from_date": anchor, "days": 30})).fetchall()
        dates = sorted({str(r[0]) for r in rows})
        print(f"engine window for 'آبادا' anchor=2026-09-16 days_forward=30: "
              f"rows={len(rows)} distinct_dates={dates}")
        print("   first row:", tuple(str(v) for v in rows[0]) if rows else None)
        print("   last  row:", tuple(str(v) for v in rows[-1]) if rows else None)
    await eng.dispose()


asyncio.run(main())
