import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        import pathlib
        for f in [".env", ".env.production"]:
            p = pathlib.Path(f)
            if p.exists():
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("DATABASE_URL="):
                        url = line.split("=", 1)[1].strip().strip("\"'")
                        break
            if url:
                break
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    eng = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with eng.connect() as c:
        r = await c.execute(text(
            "SELECT pid, now()-query_start AS dur, left(query,160) "
            "FROM pg_stat_activity WHERE datname=current_database() "
            "AND pid<>pg_backend_pid() ORDER BY query_start"))
        for row in r.fetchall():
            print(row[0], "|", row[1], "|", (row[2] or "").replace("\n", " "))
    await eng.dispose()

asyncio.run(main())
