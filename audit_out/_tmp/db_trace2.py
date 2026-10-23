"""Read-only DB aggregates for step4. No credentials printed."""
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

        await q("signal_accuracy ALL", "SELECT count(*), sum(direction_correct::int) FROM signal_accuracy")
        await q("signal_accuracy outcome_set_at NOT NULL",
                "SELECT count(*), sum(direction_correct::int) FROM signal_accuracy WHERE outcome_set_at IS NOT NULL")
        await q("by market", "SELECT market, count(*), sum(direction_correct::int) FROM signal_accuracy GROUP BY market ORDER BY 2 DESC")
        await q("by source", "SELECT source, count(*), sum(direction_correct::int) FROM signal_accuracy GROUP BY source ORDER BY 2 DESC")
        await q("paper_trades cols", "SELECT column_name FROM information_schema.columns WHERE table_name='paper_trades' ORDER BY ordinal_position")
        await q("ml_models cols", "SELECT column_name FROM information_schema.columns WHERE table_name='ml_models' ORDER BY ordinal_position")
    await eng.dispose()


asyncio.run(main())
