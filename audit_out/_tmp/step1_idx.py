import asyncio
import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

for line in Path(".env").read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())
url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)
async def main():
    eng = create_async_engine(url, future=True)
    async with eng.connect() as c:
        r = (await c.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename='brsapi_historical_daily'"
        ))).fetchall()
        for x in r: print("IDX:", x[0], "|", x[1])
        b = (await c.execute(text(
            "SELECT pg_size_pretty(pg_total_relation_size('brsapi_historical_daily'))"
        ))).fetchone()
        print("SIZE:", b[0])
        t = (await c.execute(text("SHOW statement_timeout"))).fetchone()
        print("STATEMENT_TIMEOUT:", t[0])
    await eng.dispose()
asyncio.run(main())
