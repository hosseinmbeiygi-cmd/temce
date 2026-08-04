import asyncio
import sys

sys.path.insert(0, ".")

async def main():
    from core.database import init_database
    await init_database()
    from sqlalchemy import text

    from core.database import async_session_factory
    async with async_session_factory() as s:
        r = await s.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname='public'
              AND (tablename LIKE '%crypto%' OR tablename LIKE '%gold%' OR tablename LIKE '%currency%' OR tablename LIKE '%history%')
            ORDER BY tablename
        """))
        for row in r.fetchall():
            print(row[0])

        # Check row counts
        for t in ['brsapi_crypto_prices', 'brsapi_gold_coin_prices', 'brsapi_currency_prices',
                   'brsapi_gold_coin_history', 'brsapi_gold_currency_pro_daily_history',
                   'brsapi_historical_daily']:
            try:
                r2 = await s.execute(text(f"SELECT COUNT(*) FROM {t}"))
                cnt = r2.scalar()
                print(f"  {t}: {cnt} rows")
            except Exception:
                pass

asyncio.run(main())
