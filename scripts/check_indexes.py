import asyncio
import sys

sys.path.insert(0, ".")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


async def check():
    from core.database import init_database, close_database, get_session
    from sqlalchemy import text

    await init_database()
    async for session in get_session():
        for t in ["quotes", "codal_reports", "brsapi_historical_real_legal", "brsapi_intraday_trades"]:
            r = await session.execute(
                text(f"SELECT indexname, indexdef FROM pg_indexes WHERE tablename='{t}' ORDER BY indexname")
            )
            rows = r.fetchall()
            print(f"TABLE: {t} ({len(rows)} indexes)")
            for row in rows:
                print(f"  {row[0]}")
                print(f"    {row[1][:150]}")
            print()

        # Check instrument_id column type
        r = await session.execute(
            text("SELECT data_type, character_maximum_length FROM information_schema.columns WHERE table_name='quotes' AND column_name='instrument_id'")
        )
        row = r.fetchone()
        if row:
            print(f"quotes.instrument_id type: {row[0]}")

        break
    await close_database()


asyncio.run(check())
