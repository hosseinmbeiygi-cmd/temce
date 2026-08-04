import sys

sys.path.insert(0, ".")
import asyncio


async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        # All symbols from instruments
        r = await s.execute(text("SELECT symbol, name FROM instruments WHERE symbol IS NOT NULL AND symbol != '' ORDER BY symbol"))
        rows = r.fetchall()
        print(f"Total: {len(rows)} symbols")
        print()
        for sym, name in rows:
            print(f"  {sym:<20} {name or ''}")

asyncio.run(main())
