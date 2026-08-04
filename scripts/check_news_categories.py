import asyncio

from sqlalchemy import text

from core.database import async_session_factory


async def check():
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT category, COUNT(*) as cnt FROM news_articles GROUP BY category ORDER BY cnt DESC"))
        for row in result:
            print(f"{repr(row.category):>30} : {row.cnt}")

asyncio.run(check())
