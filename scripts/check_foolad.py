import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        # Check what instrument_id looks like
        r = await s.execute(text("""
            SELECT DISTINCT instrument_id FROM codal_reports LIMIT 10
        """))
        print("Sample instrument_ids:")
        for row in r.fetchall():
            print(f"  '{row[0]}'")

        # Check if فولاد exists with any variation
        r2 = await s.execute(text("""
            SELECT symbol, instrument_id, COUNT(*) FROM codal_reports
            WHERE symbol LIKE '%فولاد%' OR instrument_id LIKE '%فولاد%'
            GROUP BY symbol, instrument_id LIMIT 5
        """))
        print("\nفولاد variations:")
        for row in r2.fetchall():
            print(f"  symbol='{row[0]}' instrument_id='{row[1]}' count={row[2]}")

asyncio.run(main())
