import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        r = await s.execute(text("""
            SELECT instrument_id, symbol, COUNT(*) as cnt
            FROM codal_reports
            WHERE symbol = 'فولاد'
            GROUP BY instrument_id, symbol
            LIMIT 5
        """))
        print("فولاد records:")
        for row in r.fetchall():
            print(f"  instrument_id='{row[0]}' symbol='{row[1]}' count={row[2]}")

        # Check if instrument_id is populated
        r2 = await s.execute(text("""
            SELECT COUNT(*) FROM codal_reports WHERE instrument_id IS NOT NULL AND instrument_id != ''
        """))
        print(f"\nRecords with instrument_id: {r2.scalar()}")

        r3 = await s.execute(text("SELECT COUNT(*) FROM codal_reports"))
        print(f"Total records: {r3.scalar()}")

asyncio.run(main())
