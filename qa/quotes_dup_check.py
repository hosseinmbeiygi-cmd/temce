import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

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
        await c.execute(text("SET statement_timeout='120000'"))
        r = await c.execute(text(
            "SELECT conname FROM pg_constraint WHERE conname='uq_quotes_symbol_date_timeframe'"))
        print("constraint:", r.fetchall())
        r = await c.execute(text("SELECT count(*) FROM quotes"))
        print("quotes_rows:", r.scalar())
        try:
            r = await c.execute(text(
                "SELECT COUNT(*) FROM (SELECT 1 FROM quotes "
                "GROUP BY symbol, date, COALESCE(timeframe,'1d') "
                "HAVING COUNT(*)>1) s"))
            print("dup_groups:", r.scalar())
        except Exception as e:
            print("dup_check_timeout_or_err:", str(e)[:200])
    await eng.dispose()

asyncio.run(main())
