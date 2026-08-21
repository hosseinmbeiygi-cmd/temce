import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure project root is on sys.path so core.config resolves
PROJECT_ROOT = str(Path(__file__).resolve().parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.config import settings  # noqa: E402


async def check():
    engine = create_async_engine(settings.database_url_async, echo=False)
    async with engine.connect() as conn:
        r = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'brsapi%' ORDER BY tablename"))
        rows = r.fetchall()
        if rows:
            print("Existing brsapi tables:")
            for row in rows:
                print(f"  - {row[0]}")
        else:
            print("No brsapi tables found. Need to create them.")
    await engine.dispose()


asyncio.run(check())
