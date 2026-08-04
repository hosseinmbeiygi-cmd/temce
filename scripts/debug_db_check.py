"""
Debug: Check backtest_runs table and understand the 0% return issue
"""
import asyncio

from sqlalchemy import text

from core.database import get_session, init_database


async def main():
    await init_database()
    async for session in get_session():
        # Check backtest_runs table
        r = await session.execute(text("""
            SELECT id, name, strategy_name, status, total_return_pct, sharpe_ratio, max_drawdown_pct
            FROM backtest_runs
            ORDER BY created_at DESC
            LIMIT 10
        """))
        rows = r.fetchall()
        print(f"Backtest runs in DB: {len(rows)}")
        for row in rows:
            print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]} | Return: {row[4]} | Sharpe: {row[5]}")

        # Check what data the backtest actually loaded
        r2 = await session.execute(text("""
            SELECT symbol, COUNT(*) as cnt, MIN(date) as min_date, MAX(date) as max_date
            FROM brsapi_historical_daily
            WHERE symbol = 'فولاد' AND price_close > 0
            GROUP BY symbol
        """))
        rows2 = r2.fetchall()
        print(f"\nفولاد historical data: {rows2}")

        # Check quotes for فولاد
        r3 = await session.execute(text("""
            SELECT symbol, COUNT(*) as cnt, MIN(date) as min_date, MAX(date) as max_date
            FROM quotes
            WHERE symbol = 'فولاد' AND price_close > 0
            GROUP BY symbol
        """))
        rows3 = r3.fetchall()
        print(f"فولاد quotes data: {rows3}")

        # Check if the date range 1402-01-01 to 1405-01-01 has data
        r4 = await session.execute(text("""
            SELECT COUNT(*) FROM brsapi_historical_daily
            WHERE symbol = 'فولاد' AND date >= '1402-01-01' AND date <= '1405-01-01'
            AND price_close > 0
        """))
        cnt = r4.scalar()
        print(f"فولاد bars in range 1402-1405: {cnt}")

        break

asyncio.run(main())
