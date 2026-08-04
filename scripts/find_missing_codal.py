import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    from core.db_utils import safe_row_str
    async with async_session_factory() as s:
        # Symbols WITHOUT codal reports
        r = await s.execute(text("""
            SELECT i.symbol, i.name
            FROM instruments i
            WHERE i.symbol IS NOT NULL AND i.symbol != ''
              AND NOT EXISTS (
                SELECT 1 FROM codal_reports c WHERE c.symbol = i.symbol
              )
            ORDER BY i.symbol
        """))
        missing = [(row[0], safe_row_str(row, idx=1)) for row in r.fetchall()]

        # Symbols WITH codal reports
        r2 = await s.execute(text("SELECT COUNT(DISTINCT symbol) FROM codal_reports"))
        has_codal = r2.scalar()

        # Total instruments
        r3 = await s.execute(text("SELECT COUNT(*) FROM instruments WHERE symbol IS NOT NULL AND symbol != ''"))
        total = r3.scalar()

        print(f"Total symbols: {total}")
        print(f"Has codal reports: {has_codal}")
        print(f"Missing codal reports: {len(missing)}")

        # Save to file
        with open("symbols_without_codal.txt", "w", encoding="utf-8") as f:
            f.write("نمادهای بدون اطلاعات کدال\n")
            f.write("========================\n")
            f.write(f"تعداد کل نمادها: {total}\n")
            f.write(f"دارای گزارش کدال: {has_codal}\n")
            f.write(f"بدون گزارش کدال: {len(missing)}\n")
            f.write(f"{'=' * 40}\n\n")
            for i, (sym, name) in enumerate(missing, 1):
                f.write(f"{i:3d}. {sym:<15} {name}\n")

        print("\nSaved to: symbols_without_codal.txt")

asyncio.run(main())
