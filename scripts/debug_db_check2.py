"""
Debug: Check backtest_runs table and understand the 0% return issue
"""
import sys

sys.path.insert(0, r"C:\Users\Iran\Desktop\temce")

import asyncio

from sqlalchemy import text

from core.database import get_session, init_database


async def main():
    await init_database()
    async for session in get_session():
        # Check backtest_runs table
        r = await session.execute(text("""
            SELECT id, name, strategy_name, status, total_return_pct, sharpe_ratio, max_drawdown_pct, current_capital, initial_capital
            FROM backtest_runs
            ORDER BY created_at DESC
            LIMIT 5
        """))
        rows = r.fetchall()
        print(f"Backtest runs in DB: {len(rows)}")
        for row in rows:
            print(f"  {row[0][:20]} | {row[1]:25s} | {row[2]:25s} | {row[3]:10s} | Return: {row[4]} | Sharpe: {row[5]} | Capital: {row[7]}/{row[8]}")

        # Check data for فولاد
        r2 = await session.execute(text("""
            SELECT symbol, COUNT(*) as cnt, MIN(date) as min_date, MAX(date) as max_date
            FROM brsapi_historical_daily
            WHERE symbol = 'فولاد' AND price_close > 0
            GROUP BY symbol
        """))
        rows2 = r2.fetchall()
        print(f"\nفولاد historical: {rows2}")

        r3 = await session.execute(text("""
            SELECT symbol, COUNT(*) as cnt, MIN(date) as min_date, MAX(date) as max_date
            FROM quotes
            WHERE symbol = 'فولاد' AND price_close > 0
            GROUP BY symbol
        """))
        rows3 = r3.fetchall()
        print(f"فولاد quotes: {rows3}")

        # Check data in date range
        r4 = await session.execute(text("""
            SELECT COUNT(*) FROM brsapi_historical_daily
            WHERE symbol = 'فولاد' AND date >= '1402-01-01' AND date <= '1405-01-01'
            AND price_close > 0
        """))
        cnt = r4.scalar()
        print(f"فولاد bars in 1402-1405: {cnt}")

        # Check what symbols have quotes data
        r5 = await session.execute(text("""
            SELECT symbol, COUNT(*) as cnt FROM quotes
            WHERE symbol IN ('فولاد', 'خودرو', 'شپنا', 'فملی', 'شستا')
            AND price_close > 0
            GROUP BY symbol
        """))
        rows5 = r5.fetchall()
        print(f"\nSymbols with quotes: {rows5}")

        break

asyncio.run(main())
