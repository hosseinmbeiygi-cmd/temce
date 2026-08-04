"""
Populate brsapi_gold_24h and brsapi_currency_24h from existing price tables.
The old Gold24h.php and Currency.php endpoints return 404, so these tables
are always empty. This script copies data from the active price tables.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from core.database import get_session, init_database


async def populate_gold_24h():
    """Copy data from gold_coin_prices to gold_24h."""
    async for session in get_session():
        r = await session.execute(text("SELECT COUNT(*) FROM brsapi_gold_coin_prices WHERE price > 0"))
        count = r.scalar()
        print(f"Gold coin prices: {count} records")

        if count == 0:
            print("No gold coin prices found — skipping")
            return

        await session.execute(text("""
            INSERT INTO brsapi_gold_24h (symbol, name, price_now, change_value, change_percent, fetched_at)
            SELECT symbol, name, price, change_value, change_percent, fetched_at
            FROM brsapi_gold_coin_prices
            WHERE price > 0
            ON CONFLICT (symbol) DO UPDATE SET
                price_now = EXCLUDED.price_now,
                change_value = EXCLUDED.change_value,
                change_percent = EXCLUDED.change_percent,
                fetched_at = EXCLUDED.fetched_at
        """))
        await session.commit()

        r = await session.execute(text("SELECT COUNT(*) FROM brsapi_gold_24h"))
        print(f"Gold 24h populated: {r.scalar()} records")
        break


async def populate_currency_24h():
    """Copy data from currency_prices to currency_24h."""
    async for session in get_session():
        r = await session.execute(text("SELECT COUNT(*) FROM brsapi_currency_prices WHERE price > 0"))
        count = r.scalar()
        print(f"Currency prices: {count} records")

        if count == 0:
            print("No currency prices found — skipping")
            return

        await session.execute(text("""
            INSERT INTO brsapi_currency_24h (symbol, name, price_now, change_value, change_percent, fetched_at)
            SELECT symbol, name, price, change_value, change_percent, fetched_at
            FROM brsapi_currency_prices
            WHERE price > 0
            ON CONFLICT (symbol) DO UPDATE SET
                price_now = EXCLUDED.price_now,
                change_value = EXCLUDED.change_value,
                change_percent = EXCLUDED.change_percent,
                fetched_at = EXCLUDED.fetched_at
        """))
        await session.commit()

        r = await session.execute(text("SELECT COUNT(*) FROM brsapi_currency_24h"))
        print(f"Currency 24h populated: {r.scalar()} records")
        break


async def main():
    await init_database()
    await populate_gold_24h()
    await populate_currency_24h()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
