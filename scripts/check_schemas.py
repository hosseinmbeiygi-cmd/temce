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
        tables = [
            "instruments",
            "quotes",
            "codal_reports",
            "brsapi_historical_real_legal",
            "brsapi_intraday_trades",
        ]
        for t in tables:
            print("=" * 60)
            print(f"TABLE: {t}")
            print("=" * 60)
            r = await session.execute(
                text(
                    f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='{t}' ORDER BY ordinal_position"
                )
            )
            for row in r.fetchall():
                nullable = "Y" if row[2] == "YES" else "N"
                print(f"  {row[0]:30} {row[1]:20} nullable={nullable}")
            print()
        break
    await close_database()


asyncio.run(check())
