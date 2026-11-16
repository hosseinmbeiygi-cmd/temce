"""Check trade_volume values."""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings


async def main():
    url = settings.database_url_async
    eng = create_async_engine(url)
    try:
        async with eng.connect() as conn:
            rows = (await conn.execute(text(
                "SELECT symbol, trade_volume, trade_value FROM brsapi_symbol_snapshots "
                "WHERE symbol IN ('MSF', 'IKCO', 'SPAS') AND trade_volume > 0 "
                "ORDER BY fetched_at DESC LIMIT 3"
            ))).fetchall()
            print("--- Sample snapshot volumes ---")
            for r in rows:
                print(f"  {r[0]}: volume={r[1]}, value={r[2]}")

            rows2 = (await conn.execute(text(
                "SELECT symbol, AVG(trade_volume) FROM brsapi_historical_daily "
                "WHERE symbol IN ('MSF', 'IKCO', 'SPAS') AND trade_volume > 0 "
                "AND gregorian_date >= CURRENT_DATE - INTERVAL '30 days' "
                "GROUP BY symbol"
            ))).fetchall()
            print("--- 30-day AVG historical volumes ---")
            for r in rows2:
                print(f"  {r[0]}: avg_volume={r[1]}")
    finally:
        await eng.dispose()

asyncio.run(main())
