"""Check brsapi_symbol_snapshots schema."""
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
            cols = (await conn.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name='brsapi_symbol_snapshots' ORDER BY ordinal_position"
            ))).fetchall()
            print("--- brsapi_symbol_snapshots columns ---")
            for c, t in cols:
                print(f"  {c}  {t}")
    finally:
        await eng.dispose()

asyncio.run(main())
