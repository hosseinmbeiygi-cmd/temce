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
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_name = 'codal_reports' ORDER BY ordinal_position
        """))
        print("codal_reports columns:")
        for row in r.fetchall():
            print(f"  {row[0]}: {row[1]}")

        r2 = await s.execute(text("SELECT COUNT(*) FROM codal_reports"))
        print(f"\nTotal rows: {r2.scalar()}")

        r3 = await s.execute(text("SELECT COUNT(DISTINCT symbol) FROM codal_reports"))
        print(f"Unique symbols: {r3.scalar()}")

asyncio.run(main())
