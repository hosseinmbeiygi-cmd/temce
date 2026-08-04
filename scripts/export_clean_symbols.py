"""خروجی نمادهای تمیز به صورت JSON."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from core.database import get_session, init_database


async def main():
    await init_database()
    async for session in get_session():
        # نمادهای تمیز (بدون پسوند عددی)
        result = await session.execute(text("""
            SELECT DISTINCT symbol
            FROM brsapi_symbol_snapshots
            WHERE symbol !~ '[0-9]+$'
            ORDER BY symbol
        """))
        symbols = [row[0] for row in result]

        # نمادهای تکراری (با پسوند عددی)
        result2 = await session.execute(text("""
            SELECT DISTINCT symbol
            FROM brsapi_symbol_snapshots
            WHERE symbol ~ '[0-9]+$'
            ORDER BY symbol
        """))
        duplicates = [row[0] for row in result2]

        data = {
            "total_clean": len(symbols),
            "total_duplicates": len(duplicates),
            "symbols": symbols,
            "duplicates": duplicates
        }

        output_file = "clean_symbols.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"فایل خروجی: {output_file}")
        print(f"نمادهای تمیز: {len(symbols)}")
        print(f"نمادهای تکراری: {len(duplicates)}")
        break


asyncio.run(main())
