import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        # Symbols in BOTH tables
        r = await s.execute(text("""
            SELECT i.symbol, i.name
            FROM instruments i
            INNER JOIN codal_reports c ON i.symbol = c.symbol
            GROUP BY i.symbol, i.name
            ORDER BY i.symbol
            LIMIT 20
        """))
        print("Symbols in BOTH instruments and codal_reports:")
        for row in r.fetchall():
            print(f"  {row[0]} - {row[1]}")

        # Test with first symbol
        r2 = await s.execute(text("""
            SELECT symbol, instrument_id FROM codal_reports WHERE symbol = 'آبادا' LIMIT 3
        """))
        print("\nآبادا records:")
        for row in r2.fetchall():
            print(f"  symbol='{row[0]}' instrument_id='{row[1]}'")

asyncio.run(main())
