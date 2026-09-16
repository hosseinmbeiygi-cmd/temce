import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.ids import new_id
from core.time import utc_now_naive
from models.instrument import InstrumentModel
from models.quote import QuoteModel
from services.tsetmc_client import TsetmcClient

DATABASE_URL = "sqlite+aiosqlite:///data/market.db"

async def reliable_ingest(symbol: str, ins_code: str):
    # 1. دریافت داده از TSETMC
    print(f"📡 دریافت داده برای {symbol}...")
    client = TsetmcClient()
    result = await client.get_closing_price_info(ins_code)

    if not result.success:
        print(f"❌ خطا در دریافت: {result.error}")
        return

    data = result.value
    print("✅ داده دریافت شد (نمونه):")
    print(f"   pClosing: {data.get('pClosing')}")
    print(f"   pDrCotVal: {data.get('pDrCotVal')}")
    print(f"   zTotTran: {data.get('zTotTran')}")

    # 2. اتصال به دیتابیس
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 3. پیدا کردن instrument_id
        stmt = select(InstrumentModel).where(InstrumentModel.symbol == symbol)
        instrument = (await session.execute(stmt)).scalar_one_or_none()

        if not instrument:
            print(f"❌ نماد {symbol} در دیتابیس وجود ندارد")
            return

        print(f"✅ instrument_id پیدا شد: {instrument.id}")

        # 4. ساخت Quote جدید با داده‌های واقعی
        # 🔥 از pClosing به عنوان قیمت پایانی استفاده می‌کنیم
        p_close = data.get('pClosing', 0)
        if p_close == 0:
            # اگر pClosing صفر بود، از pDrCotVal استفاده کن
            p_close = data.get('pDrCotVal', 0)

        new_quote = QuoteModel(
            id=new_id("quote"),
            instrument_id=instrument.id,
            price_close=p_close,
            price_last=data.get('pDrCotVal', p_close),
            price_open=data.get('priceFirst', 0),
            price_high=data.get('priceMax', 0),
            price_low=data.get('priceMin', 0),
            price_change=data.get('priceChange', 0),
            price_yesterday=data.get('priceYesterday', 0),
            volume=data.get('zTotTran', 0),
            value=data.get('qTotTran5J', 0),
            trade_count=data.get('nvt', 0),
            date=utc_now_naive().strftime("%Y-%m-%d"),
            time=utc_now_naive().strftime("%H:%M:%S"),
            timeframe="1d",
            data_source="tsetmc"
        )

        # 5. ذخیره در دیتابیس با بررسی خطا
        try:
            session.add(new_quote)
            await session.commit()
            print(f"✅ داده برای {symbol} با قیمت {p_close} ذخیره شد.")
        except Exception as e:
            print(f"❌ خطا در ذخیره‌سازی: {e}")
            await session.rollback()
            return

        # 6. بررسی اینکه آیا رکورد واقعاً ذخیره شده است
        stmt_check = select(QuoteModel).where(QuoteModel.instrument_id == instrument.id).order_by(QuoteModel.created_at.desc()).limit(1)
        latest = (await session.execute(stmt_check)).scalar_one_or_none()

        if latest:
            print(f"✅ تأیید: آخرین قیمت ذخیره‌شده: {latest.price_close}")
            print(f"📊 شناسه رکورد: {latest.id}")
        else:
            print("❌ هیچ رکوردی در دیتابیس پیدا نشد!")

if __name__ == "__main__":
    # 🔥 کد عددی صحیح (insCode) را اینجا قرار دهید
    asyncio.run(reliable_ingest("فولاد", "46348559193224090"))
