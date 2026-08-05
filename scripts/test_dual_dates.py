"""Validate the dual-date functions against jdatetime + trigger end-to-end.

Requires scripts/install_dual_dates.py to have run first.

Usage:
    python scripts/test_dual_dates.py
"""
from __future__ import annotations

import asyncio
import datetime
import os
import random

import jdatetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from scripts._db import database_url_async

    DB_URL = database_url_async()
except Exception:  # pragma: no cover
    DB_URL = os.environ.get("DATABASE_URL")


async def main() -> None:
    engine = create_async_engine(DB_URL)
    async with engine.connect() as c:
        # reference sanity
        for q, lab in [
            ("SELECT shamsi_to_miladi('1400-01-01'), shamsi_to_miladi('1405-05-10')", "s2m ref"),
            ("SELECT miladi_to_shamsi(make_date(2021,3,21)), miladi_to_shamsi(make_date(2026,7,15))", "m2s ref"),
            ("SELECT * FROM _jal_cal(1400)", "jal 1400"),
        ]:
            print(lab, "->", (await c.execute(text(q))).fetchall())

        random.seed(42)
        fails = 0
        total = 0

        # shamsi -> miladi
        for _ in range(400):
            jy = random.randint(1300, 1410)
            jm = random.randint(1, 12)
            jd = random.randint(1, 28)
            try:
                expect = jdatetime.date(jy, jm, jd).togregorian()
            except Exception:
                continue
            total += 1
            got = (await c.execute(text("SELECT shamsi_to_miladi(:s)"), {"s": f"{jy}-{jm:02d}-{jd:02d}"})).scalar()
            if got != expect:
                fails += 1
                if fails < 6:
                    print("MISMATCH s2m", jy, jm, jd, "SQL=", got, "exp=", expect)

        # miladi -> shamsi
        for _ in range(400):
            g = datetime.date(random.randint(1995, 2030), random.randint(1, 12), random.randint(1, 28))
            expect = jdatetime.date.fromgregorian(day=g.day, month=g.month, year=g.year)
            exp_s = f"{expect.year}-{expect.month:02d}-{expect.day:02d}"
            got = (await c.execute(text("SELECT miladi_to_shamsi(:d)"), {"d": g})).scalar()
            if got != exp_s:
                fails += 1
                if fails < 6:
                    print("MISMATCH m2s", g, "SQL=", got, "exp=", exp_s)

        print(f"CONVERSION: total={total} fails={fails}")

        # format classifier
        samples = [
            "1405-05-10",
            "'1405-05-10'",
            "1405/04/24",
            "۱۴۰۵/۰۴/۳۱",
            "2026-07-27T12:19:53.781Z",
            "2026-07-27 12:19:53+00",
            "1405.04.24",
            "0000-00-00",
            "15:49:16",
            None,
        ]
        for s in samples:
            got = (await c.execute(text("SELECT any_to_miladi(:v)"), {"v": s})).scalar()
            print("any_to_miladi", repr(s), "->", got)

        # trigger end-to-end on a temp table
        await c.execute(text("CREATE TEMP TABLE _dual_t (id int, trade_date text, gregorian_date date, shamsi_date varchar(10))"))
        await c.execute(
            text(
                "INSERT INTO dual_date_columns (table_name, source_column) VALUES ('_dual_t', 'trade_date') "
                "ON CONFLICT (table_name) DO UPDATE SET source_column = EXCLUDED.source_column"
            )
        )
        await c.execute(text("CREATE TRIGGER trg_dual_dates BEFORE INSERT OR UPDATE ON _dual_t FOR EACH ROW EXECUTE FUNCTION sync_dual_dates_fn()"))
        await c.execute(text("INSERT INTO _dual_t (id, trade_date) VALUES (1, '1405-05-10')"))
        await c.execute(text("INSERT INTO _dual_t (id, trade_date) VALUES (2, '2026-07-27T12:19:53Z')"))
        await c.execute(text("INSERT INTO _dual_t (id, trade_date) VALUES (3, NULL)"))
        rows = (await c.execute(text("SELECT * FROM _dual_t ORDER BY id"))).fetchall()
        for r in rows:
            print("TRIGGER ROW:", r)
        await c.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
