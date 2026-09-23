import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
load_dotenv()

async def main():
    e = create_async_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT")
    async with e.connect() as c:
        # Bounded to ONE symbol -> fast.
        r = (await c.execute(text("""
            select symbol, date, count(*) n,
                   count(distinct price_last) d_last,
                   count(distinct trade_volume) d_vol,
                   count(distinct coalesce(ins_id,'')) d_ins,
                   count(distinct created_at::date) d_days
            from brsapi_historical_daily
            where symbol = (select symbol from brsapi_historical_daily limit 1)
            group by symbol, date having count(*)>1
            order by n desc limit 10
        """))).fetchall()
        print("=== per-symbol dup groups: do the price fields actually differ? ===")
        print("   symbol date n | distinct(price_last) distinct(volume) distinct(ins_id) distinct(fetch-days)")
        for x in r: print("  ", tuple(x))
        print("\n=== is 'row' populated in intraday_trades (potential natural key)? ===")
        r = (await c.execute(text("""
            select count(*) total,
                   count("row") row_filled,
                   count(distinct "row") row_distinct
            from brsapi_intraday_trades where symbol=(select symbol from brsapi_intraday_trades limit 1)
        """))).fetchone()
        print("   total=%s row_non_null=%s row_distinct=%s" % tuple(r))
        r = (await c.execute(text("""
            select symbol, trade_date, time, price, volume, "row", count(*) n
            from brsapi_intraday_trades
            where symbol=(select symbol from brsapi_intraday_trades limit 1)
            group by 1,2,3,4,5,6 having count(*)>1 order by n desc limit 5
        """))).fetchall()
        print("   identical full-key groups (symbol,trade_date,time,price,volume,row):")
        for x in r: print("    ", tuple(x))
    await e.dispose()
asyncio.run(main())
