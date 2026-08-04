import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        # All unique symbols in codal_reports
        r = await s.execute(text("""
            SELECT DISTINCT symbol FROM codal_reports ORDER BY symbol LIMIT 30
        """))
        print("First 30 symbols in codal_reports:")
        for row in r.fetchall():
            print(f"  {row[0]}")

        # Check total unique symbols
        r2 = await s.execute(text("SELECT COUNT(DISTINCT symbol) FROM codal_reports"))
        print(f"\nTotal unique symbols: {r2.scalar()}")

        # Check if فولاد exists in instruments
        r3 = await s.execute(text("SELECT symbol FROM instruments WHERE symbol = 'فولاد'"))
        row = r3.fetchone()
        print(f"\nفولاد in instruments: {'YES' if row else 'NO'}")

asyncio.run(main())
