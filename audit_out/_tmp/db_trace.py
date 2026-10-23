"""Read-only DB counts for step4 traceability. Prints no credentials."""
import asyncio
import os
import re
from pathlib import Path

env = Path(".env")
for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

url = os.environ.get("DATABASE_URL", "")
if url.startswith("postgresql://"):
    url = "postgresql+asyncpg://" + url[len("postgresql://"):]
elif url.startswith("postgres://"):
    url = "postgresql+asyncpg://" + url[len("postgres://"):]
safe = re.sub(r"//[^@]*@", "//***@", url)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    print("target:", safe)
    eng = create_async_engine(url, future=True)
    async with eng.connect() as c:
        for tbl in ["signal_accuracy", "paper_trades", "paper_equity_history", "ml_models", "backtest_runs"]:
            try:
                n = (await c.execute(text(f"SELECT count(*) FROM {tbl}"))).scalar()
                print(f"{tbl} = {n}")
            except Exception as e:
                print(f"{tbl} = ERROR {type(e).__name__}: {e}")
        try:
            cols = (await c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='signal_accuracy' ORDER BY ordinal_position"))).scalars().all()
            print("signal_accuracy columns:", cols)
        except Exception as e:
            print("columns ERROR:", e)
    await eng.dispose()


asyncio.run(main())
