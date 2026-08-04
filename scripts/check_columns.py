import asyncio
import sys

sys.path.insert(0, ".")

async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        for t in ['brsapi_gold_coin_history', 'brsapi_gold_currency_pro_daily_history']:
            r = await s.execute(text(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{t}'
                ORDER BY ordinal_position
            """))
            print(f"\n=== {t} ===")
            for row in r.fetchall():
                print(f"  {row[0]}: {row[1]} (nullable={row[2]})")

asyncio.run(main())
