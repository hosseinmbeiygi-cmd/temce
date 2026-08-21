import asyncio, io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")
import asyncpg

# Credentials come from settings/.env — never hardcode them in scripts.
try:
    from scripts._db import database_url_async
    DB_URL = database_url_async().replace("+asyncpg", "")
except Exception:  # pragma: no cover
    DB_URL = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")

async def main():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("""
        SELECT id, created_at, gregorian_date, shamsi_date, date
        FROM brsapi_shareholder_records WHERE date IS NULL LIMIT 4
    """)
    for r in rows:
        print('created_at=', r['created_at'], '| gregorian=', r['gregorian_date'], '| shamsi=', r['shamsi_date'])
    # column types
    t = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='brsapi_shareholder_records' AND column_name IN ('created_at','date','gregorian_date')")
    print('types:', [(r['column_name'], r['data_type']) for r in t])
    await conn.close()

asyncio.run(main())
