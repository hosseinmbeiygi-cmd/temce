import json
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
        r = await s.execute(text("SELECT symbol, name FROM instruments WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol"))
        symbols = [{"symbol": row[0], "name": safe_row_str(row, idx=1)} for row in r.fetchall()]
        with open("symbols_list.json", "w", encoding="utf-8") as f:
            json.dump(symbols, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(symbols)} symbols to symbols_list.json")

asyncio.run(main())
