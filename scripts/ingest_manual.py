import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import asyncio
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.instrument import InstrumentModel
from core.ids import new_id

DATABASE_URL = "sqlite+aiosqlite:///data/market.db"

async def add_instrument():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        stmt = insert(InstrumentModel).values(
            id=new_id("inst"),
            symbol="فولاد",
            name="فولاد مبارکه اصفهان",
            ins_code="IRO1FOLD0001",
            market_type="bours"
        )
        await session.execute(stmt)
        await session.commit()
        print("✅ نماد فولاد با موفقیت به دیتابیس اضافه شد.")

if __name__ == "__main__":
    asyncio.run(add_instrument())