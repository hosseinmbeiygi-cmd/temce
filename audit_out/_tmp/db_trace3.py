"""Read-only paper_trades aggregates for step4. No credentials printed."""
import asyncio
import os
from pathlib import Path

for line in Path(".env").read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    eng = create_async_engine(url, future=True)
    async with eng.connect() as c:
        async def q(label, sql):
            try:
                rows = (await c.execute(text(sql))).fetchall()
                print(f"--- {label} ---")
                for r in rows:
                    print("  ", r)
            except Exception as e:
                print(f"--- {label} ERROR: {type(e).__name__}: {e}")

        await q("paper_trades totals",
                "SELECT count(*), count(*) FILTER (WHERE pnl>0), sum(pnl), avg(pnl_pct), sum(pnl_pct), count(DISTINCT symbol) FROM paper_trades")
        await q("paper_trades by status", "SELECT status, count(*) FROM paper_trades GROUP BY status")
        await q("last signal_accuracy date",
                "SELECT max(gregorian_date), max(shamsi_date), max(outcome_set_at) FROM signal_accuracy")
    await eng.dispose()


asyncio.run(main())
