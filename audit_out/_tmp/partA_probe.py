"""Read-only probe: DB connectivity + brsapi_historical_daily schema. No writes."""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import settings


async def main() -> None:
    url = settings.database_url_async
    safe = url.split("@")[-1] if "@" in url else url
    print("database_url_async (host part only):", safe)
    print("driver:", url.split(":")[0])
    eng = create_async_engine(url)
    try:
        async with eng.connect() as conn:
            rows = (await conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' ORDER BY table_name"
            ))).fetchall()
            names = [r[0] for r in rows]
            print("public tables count:", len(names))
            for n in names:
                print("  ", n)
            # columns of brsapi_historical_daily
            cols = (await conn.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name='brsapi_historical_daily' ORDER BY ordinal_position"
            ))).fetchall()
            print("--- brsapi_historical_daily columns ---")
            for c, t in cols:
                print(f"  {c}  {t}")
    finally:
        await eng.dispose()


asyncio.run(main())
