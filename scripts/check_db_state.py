import asyncio
import sys

sys.path.insert(0, ".")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


async def check():
    from sqlalchemy import text

    from core.database import close_database, get_session, init_database

    await init_database()
    async for session in get_session():
        r = await session.execute(
            text("SELECT EXISTS (SELECT FROM pg_matviews WHERE matviewname='symbol_kpi_view')")
        )
        print("View exists:", r.scalar())

        for t in ["quotes", "instruments", "codal_reports", "brsapi_historical_real_legal", "brsapi_intraday_trades"]:
            try:
                r = await session.execute(text(f"SELECT COUNT(*) FROM {t}"))
                c = r.scalar() or 0
                print(f"{t}: {c:,}")
            except Exception as e:
                print(f"{t}: ERROR - {str(e)[:50]}")
        break
    await close_database()


asyncio.run(check())
