"""Read-only inspection: duplicates, hypertables, constraints on the hot BrsApi tables."""
from __future__ import annotations

import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

load_dotenv()
URL = os.environ["DATABASE_URL"]

TABLES = [
    "brsapi_historical_daily",
    "brsapi_historical_real_legal",
    "brsapi_intraday_trades",
    "brsapi_candlesticks",
    "brsapi_symbol_snapshots",
]


async def main() -> None:
    eng = create_async_engine(URL, isolation_level="AUTOCOMMIT")
    async with eng.connect() as c:
        db = (await c.execute(text("select current_database()"))).scalar()
        print(f"database = {db}")
        alembic = (await c.execute(text(
            "select version_num from alembic_version"
        ))).scalars().all()
        print(f"alembic_version = {list(alembic)}")
        ts = (await c.execute(text(
            "select extname, extversion from pg_extension where extname='timescaledb'"
        ))).fetchall()
        print(f"timescaledb = {list(ts)}")

        print("\n=== hypertables ===")
        rows = (await c.execute(text("""
            select hypertable_name, num_dimensions, compression_enabled
            from timescaledb_information.hypertables order by hypertable_name
        """))).fetchall() if ts else []
        for r in rows:
            print("  ", tuple(r))

        for t in TABLES:
            print(f"\n=== {t} ===")
            kind = (await c.execute(text("""
                select c.relkind from pg_class c
                join pg_namespace n on n.oid=c.relnamespace
                where n.nspname='public' and c.relname=:t
            """), {"t": t})).scalar()
            if kind is None:
                print("   MISSING")
                continue
            print("   relkind:", {"r": "table", "p": "partitioned", "v": "view"}.get(kind, kind))
            approx = (await c.execute(text(
                "select reltuples::bigint from pg_class where relname=:t"
            ), {"t": t})).scalar()
            print("   reltuples:", approx)
            cons = (await c.execute(text("""
                select conname, pg_get_constraintdef(oid)
                from pg_constraint where conrelid = cast(:t as regclass)
                order by conname
            """), {"t": t})).fetchall()
            for x in cons:
                print("   constraint:", x[0], "->", x[1])
            idx = (await c.execute(text("""
                select indexname, indexdef from pg_indexes where tablename=:t
                order by indexname
            """), {"t": t})).fetchall()
            for x in idx:
                print("   index:", x[0], "->", x[1])

        print("\n=== duplicate groups (symbol,date) ===")
        for t, datecol in [("brsapi_historical_daily", "date"),
                           ("brsapi_historical_real_legal", "date"),
                           ("brsapi_candlesticks", "date")]:
            try:
                r = (await c.execute(text(f"""
                    select count(*) as grp, coalesce(sum(cnt)-count(*),0) as extra
                    from (select count(*) cnt from {t} group by symbol, {datecol}
                          having count(*)>1) s
                """))).fetchone()
                print(f"  {t}: dup_groups={r[0]} redundant_rows={r[1]}")
            except Exception as e:
                print(f"  {t}: ERROR {type(e).__name__}: {str(e)[:120]}")
                await c.rollback() if hasattr(c, "rollback") else None

        print("\n=== intraday dup (symbol, time, trade_date) ===")
        try:
            r = (await c.execute(text("""
                select count(*) grp, coalesce(sum(cnt)-count(*),0) extra
                from (select count(*) cnt from brsapi_intraday_trades
                      group by symbol, time, trade_date having count(*)>1) s
            """))).fetchone()
            print("  ", tuple(r))
        except Exception as e:
            print("   ERROR", str(e)[:150])

    await eng.dispose()


asyncio.run(main())
