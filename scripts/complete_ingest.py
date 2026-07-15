import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.ids import new_id
from models.instrument import InstrumentModel
from models.quote import QuoteModel
from services.tsetmc_client import TsetmcClient

DATABASE_URL = "sqlite+aiosqlite:///data/market.db"

async def fetch_and_save(symbol: str, ins_code: str):
    # 1. دریافت داده از TSETMC
    print(f"📡 دریافت داده برای {symbol}...")
    client = TsetmcClient()
    result = await client.get_closing_price_info(ins_code)

    if not result.success:
        print(f"❌ خطا در دریافت: {result.error}")
        return

    data = result.value
    print("✅ داده دریافت شد:")
    print(data)

    # 2. اتصال به دیتابیس
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 3. پیدا کردن instrument_id برای نماد
        stmt = select(InstrumentModel).where(InstrumentModel.symbol == symbol)
        instrument = (await session.execute(stmt)).scalar_one_or_none()

        if not instrument:
            print(f"❌ نماد {symbol} در دیتابیس وجود ندارد")
            return

        # 4. استخراج داده‌ها از پاسخ TSETMC
        # توجه: ممکن است کلیدها متفاوت باشند
        p_close = data.get('pClosing', 0)
        p_last = data.get('pDrCotVal', p_close)
        p_open = data.get('priceFirst', 0)  # ممکن است null باشد
        p_high = data.get('priceMax', 0)
        p_low = data.get('priceMin', 0)
        volume = data.get('zTotTran', 0)
        value = data.get('qTotTran5J', 0)
        trade_count = data.get('nvt', 0)  # تعداد معاملات (ممکن است نادرست باشد)

        # 5. ساخت یک Quote جدید
        new_quote = QuoteModel(
            id=new_id("quote"),
            instrument_id=instrument.id,
            price_close=p_close,
            price_last=p_last,
            price_open=p_open,
            price_high=p_high,
            price_low=p_low,
            price_change=data.get('priceChange', 0),
            price_yesterday=data.get('priceYesterday', 0),
            volume=volume,
            value=value,
            trade_count=trade_count,
            date=datetime.now().strftime("%Y-%m-%d"),
            time=datetime.now().strftime("%H:%M:%S"),
            timeframe="1d",
            data_source="tsetmc"
        )

        # 6. ذخیره در دیتابیس
        session.add(new_quote)
        await session.commit()
        print(f"✅ داده برای {symbol} با قیمت {p_close} ذخیره شد.")

        # 7. نمایش آخرین داده‌های ذخیره شده برای این نماد
        stmt_latest = select(QuoteModel).where(QuoteModel.instrument_id == instrument.id).order_by(QuoteModel.created_at.desc()).limit(1)
        latest = (await session.execute(stmt_latest)).scalar_one_or_none()
        if latest:
            print(f"📊 آخرین قیمت ذخیره‌شده: {latest.price_close}")

if __name__ == "__main__":
    # 🔥 کد عددی صحیح (insCode) را اینجا قرار دهید
    asyncio.run(fetch_and_save("فولاد", "46348559193224090"))
