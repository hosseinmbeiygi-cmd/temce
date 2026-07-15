import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from models.instrument import InstrumentModel
from models.quote import QuoteModel

DATABASE_URL = "sqlite+aiosqlite:///data/market.db"

async def check_quote():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. پیدا کردن instrument_id برای نماد "فولاد"
        stmt_instr = select(InstrumentModel).where(InstrumentModel.symbol == "فولاد")
        instrument = (await session.execute(stmt_instr)).scalar_one_or_none()

        if not instrument:
            print("❌ نماد 'فولاد' در دیتابیس وجود ندارد.")
            return

        print(f"✅ instrument_id پیدا شد: {instrument.id}")

        # 2. جستجوی آخرین قیمت برای این instrument_id
        stmt_quote = select(QuoteModel).where(QuoteModel.instrument_id == instrument.id).order_by(QuoteModel.created_at.desc()).limit(1)
        latest_quote = (await session.execute(stmt_quote)).scalar_one_or_none()

        if latest_quote:
            print(f"✅ آخرین قیمت: {latest_quote.price_close}")
            print(f"   تاریخ: {latest_quote.date}")
            print(f"   زمان: {latest_quote.time}")
        else:
            print("❌ هیچ رکوردی برای این instrument_id پیدا نشد.")

        # 3. تعداد کل رکوردهای quotes
        count_stmt = select(text("COUNT(*)")).select_from(QuoteModel)
        total = (await session.execute(count_stmt)).scalar()
        print(f"\n📊 تعداد کل رکوردهای quotes: {total}")

if __name__ == "__main__":
    asyncio.run(check_quote())
