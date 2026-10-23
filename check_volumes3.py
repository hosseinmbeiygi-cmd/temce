"""Check trade_volume values - simple query."""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from core.config import settings

async def main():
    url = settings.database_url_async
    eng = create_async_engine(url, connect_args={"timeout": 5})
    try:
        async with eng.connect() as conn:
            rows = (await conn.execute(text(
                "SELECT symbol, trade_volume FROM brsapi_symbol_snapshots "
                "WHERE trade_volume > 0 ORDER BY fetched_at DESC LIMIT 5"
            ))).fetchall()
            print("--- Sample snapshot volumes ---")
            for r in rows:
                sym = str(r[0]).encode('ascii', 'replace').decode('ascii')
                print(f"  {sym}: volume={r[1]}")
    finally:
        await eng.dispose()

asyncio.run(main())