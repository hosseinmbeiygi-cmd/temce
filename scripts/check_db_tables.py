import asyncio

from sqlalchemy import text

from core.database import async_session_factory


async def main():
    if not async_session_factory:
        print("Database not initialized")
        return
    async with async_session_factory() as sess:
        for tbl in ["brsapi_historical_daily", "quotes", "signals", "instruments"]:
            try:
                r = await sess.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                print(f"  {tbl}: {r.scalar()} rows")
            except Exception as e:
                print(f"  {tbl}: ERROR - {e}")


asyncio.run(main())
