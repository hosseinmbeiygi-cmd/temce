"""Read-only aggregates for the consolidated report. No credentials printed."""
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
        await q("signal_accuracy cols",
                "SELECT column_name FROM information_schema.columns WHERE table_name='signal_accuracy' ORDER BY ordinal_position")
        await q("signal_accuracy aggregates",
                "SELECT count(*), count(*) FILTER (WHERE direction_correct), "
                "round(avg(actual_return_pct)::numeric,4), "
                "count(*) FILTER (WHERE actual_return_pct>0) FROM signal_accuracy")
        await q("signal_accuracy outcome-set only",
                "SELECT count(*), count(*) FILTER (WHERE direction_correct), round(avg(actual_return_pct)::numeric,4) "
                "FROM signal_accuracy WHERE outcome_set_at IS NOT NULL")
        await q("paper_trades winrate + pnl",
                "SELECT count(*), count(*) FILTER (WHERE pnl>0), round(sum(pnl)::numeric,2) FROM paper_trades")
        await q("date spans",
                "SELECT max(shamsi_date), max(gregorian_date) FROM signal_accuracy")
        await q("acceptance.yaml?", "SELECT 1")
    await eng.dispose()
asyncio.run(main())
