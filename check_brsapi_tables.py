import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def check():
    engine = create_async_engine("postgresql+asyncpg://hossein:1343@localhost:5432/my_first_db", echo=False)
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
