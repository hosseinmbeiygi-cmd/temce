import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.instrument import InstrumentModel
from models.quote import QuoteModel
from core.ids import new_id
from datetime import datetime

DATABASE_URL = "sqlite+aiosqlite:///data/market.db"

async def final_ingest(symbol: str, ins_code: str):
    # 1. دریافت داده از TSETMC با استفاده از httpx
    import httpx
    url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ins_code}"
    print(f"📡 درخواست به: {url}")
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url)
    
    if response.status_code != 200:
        print(f"❌ خطا: {response.status_code} - {response.text}")
        return
    
    data = response.json()
    print("✅ داده دریافت شد.")
    
    # 🔥 دسترسی به closingPriceInfo
    closing_info = data.get("closingPriceInfo")
    if not closing_info:
        print("❌ ساختار داده نامعتبر است (closingPriceInfo وجود ندارد)")
        return
    
    # استخراج فیلدهای مورد نیاز
    p_close = closing_info.get('pClosing', 0)
    p_dr_cot_val = closing_info.get('pDrCotVal', 0)
    volume = closing_info.get('zTotTran', 0)
    price_yesterday = closing_info.get('priceYesterday', 0)
    price_change = closing_info.get('priceChange', 0)
    price_first = closing_info.get('priceFirst', 0)
    price_min = closing_info.get('priceMin', 0)
    price_max = closing_info.get('priceMax', 0)
    trade_count = closing_info.get('nvt', 0)
    value = closing_info.get('qTotTran5J', 0)
    date_int = closing_info.get('dEven', 0)  # عددی مثل 20260622
    time_int = closing_info.get('hEven', 0)  # عددی مثل 61021
    
    print(f"📊 قیمت پایانی: {p_close}")
    print(f"📊 قیمت آخرین معامله: {p_dr_cot_val}")
    print(f"📊 حجم معاملات: {volume}")
    print(f"📊 وضعیت: {closing_info.get('instrumentState', {}).get('cEtavalTitle', 'نامشخص')}")
    
    if p_close == 0:
        print("⚠️ قیمت پایانی صفر است، اما ادامه می‌دهیم...")
    
    # 2. اتصال به دیتابیس
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # پیدا کردن instrument_id
        stmt = select(InstrumentModel).where(InstrumentModel.symbol == symbol)
        instrument = (await session.execute(stmt)).scalar_one_or_none()
        if not instrument:
            print(f"❌ نماد {symbol} در دیتابیس وجود ندارد")
            return
        
        # ساخت رکورد Quote
        new_quote = QuoteModel(
            id=new_id("quote"),
            instrument_id=instrument.id,
            price_close=p_close,
            price_last=p_dr_cot_val,
            price_open=price_first,
            price_high=price_max,
            price_low=price_min,
            price_change=price_change,
            price_yesterday=price_yesterday,
            volume=volume,
            value=value,
            trade_count=int(trade_count) if trade_count else 0,
            date=str(date_int) if date_int else datetime.now().strftime("%Y-%m-%d"),
            time=str(time_int) if time_int else datetime.now().strftime("%H:%M:%S"),
            timeframe="1d",
            data_source="tsetmc"
        )
        
        # ذخیره‌سازی
        try:
            session.add(new_quote)
            await session.commit()
            print(f"✅ داده برای {symbol} با قیمت {p_close} ذخیره شد.")
        except Exception as e:
            print(f"❌ خطا در ذخیره‌سازی: {e}")
            await session.rollback()
            return
        
        # تأیید نهایی
        stmt_check = select(QuoteModel).where(QuoteModel.instrument_id == instrument.id).order_by(QuoteModel.created_at.desc()).limit(1)
        latest = (await session.execute(stmt_check)).scalar_one_or_none()
        if latest:
            print(f"✅ تأیید: آخرین قیمت ذخیره‌شده: {latest.price_close}")
        else:
            print("❌ خطا: رکوردی در دیتابیس پیدا نشد!")

if __name__ == "__main__":
    asyncio.run(final_ingest("فولاد", "46348559193224090"))