#!/usr/bin/env python
"""Check row counts for symbols used in train_all_models.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import settings


async def main():
    engine = create_async_engine(settings.database_url_async, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        symbols = ['فولاد', 'فملی', 'وبانک', 'کگل', 'خودرو', 'شستا', 'شپنا']
        for sym in symbols:
            result = await session.execute(
                text("SELECT COUNT(*) FROM brsapi_historical_daily WHERE symbol = :sym"),
                {"sym": sym}
            )
            cnt = result.scalar() or 0
            print(f"  {sym}: {cnt} rows")

        # Also check total
        result = await session.execute(text("SELECT COUNT(*) FROM brsapi_historical_daily"))
        total = result.scalar() or 0
        print(f"\nTotal rows in brsapi_historical_daily: {total}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
