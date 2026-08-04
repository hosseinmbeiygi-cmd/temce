import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        # Symbols in instruments but NOT in codal_reports
        r = await s.execute(text("""
            SELECT i.symbol FROM instruments i
            WHERE NOT EXISTS (SELECT 1 FROM codal_reports c WHERE c.symbol = i.symbol)
            AND i.symbol IS NOT NULL AND i.symbol != ''
            ORDER BY i.symbol
            LIMIT 20
        """))
        print("Symbols in instruments but NOT in codal_reports (first 20):")
        for row in r.fetchall():
            print(f"  {row[0]}")

        # Symbols in codal_reports but NOT in instruments
        r2 = await s.execute(text("""
            SELECT c.symbol FROM codal_reports c
            WHERE NOT EXISTS (SELECT 1 FROM instruments i WHERE i.symbol = c.symbol)
            AND c.symbol IS NOT NULL
            GROUP BY c.symbol
            ORDER BY c.symbol
            LIMIT 20
        """))
        print("\nSymbols in codal_reports but NOT in instruments (first 20):")
        for row in r2.fetchall():
            print(f"  {row[0]}")

asyncio.run(main())
