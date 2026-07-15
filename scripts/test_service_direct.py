# scripts/test_service_direct.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from services.quote_service import QuoteService


async def test():
    engine = create_async_engine("sqlite+aiosqlite:///data/market.db")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        service = QuoteService(session=session)
        result = await service.get_latest("inst_f2d6ced51130")
        if result.success:
            print(f"✅ قیمت: {result.value.price_close}")
        else:
            print(f"❌ خطا: {result.error}")

if __name__ == "__main__":
    asyncio.run(test())
