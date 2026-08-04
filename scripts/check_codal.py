import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        r = await s.execute(text("SELECT DISTINCT symbol FROM codal_reports ORDER BY symbol"))
        symbols = [row[0] for row in r.fetchall()]
        print(f"Total symbols in codal_reports: {len(symbols)}")
        # Check which have recent data
        r2 = await s.execute(text("""
            SELECT symbol, MAX(date) as max_date, COUNT(*) as cnt
            FROM codal_reports
            GROUP BY symbol
            ORDER BY max_date DESC NULLS LAST
            LIMIT 10
        """))
        print("\nTop 10 by latest date:")
        for row in r2.fetchall():
            print(f"  {row[0]}: {row[1]} ({row[2]} records)")

        r3 = await s.execute(text("""
            SELECT symbol, MAX(date) as max_date
            FROM codal_reports
            WHERE date < '1405-01-01'
            GROUP BY symbol
            ORDER BY max_date ASC
            LIMIT 10
        """))
        print("\nSymbols needing update (oldest first):")
        for row in r3.fetchall():
            print(f"  {row[0]}: last={row[1]}")

        r4 = await s.execute(text("SELECT COUNT(DISTINCT symbol) FROM codal_reports"))
        print(f"\nTotal unique symbols: {r4.scalar()}")

        # All symbols from instruments
        r5 = await s.execute(text("SELECT DISTINCT symbol FROM instruments ORDER BY symbol"))
        all_syms = [row[0] for row in r5.fetchall()]
        print(f"Total symbols in instruments: {len(all_syms)}")

        # Symbols not in codal_reports
        r6 = await s.execute(text("""
            SELECT DISTINCT i.symbol FROM instruments i
            WHERE NOT EXISTS (SELECT 1 FROM codal_reports c WHERE c.symbol = i.symbol)
            ORDER BY i.symbol
        """))
        missing = [row[0] for row in r6.fetchall()]
        print(f"Symbols missing from codal_reports: {len(missing)}")

asyncio.run(main())
