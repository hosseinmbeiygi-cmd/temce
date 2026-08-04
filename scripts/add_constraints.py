import asyncio
import sys

sys.path.insert(0, ".")

async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        # Add UNIQUE constraints if not exist
        for tbl in ['brsapi_gold_coin_history', 'brsapi_gold_currency_pro_daily_history']:
            try:
                await s.execute(text(f"ALTER TABLE {tbl} ADD CONSTRAINT uq_{tbl}_sym_date UNIQUE (symbol, date)"))
                await s.commit()
                print(f"Added UNIQUE constraint to {tbl}")
            except Exception as e:
                print(f"{tbl}: {e}")

asyncio.run(main())
