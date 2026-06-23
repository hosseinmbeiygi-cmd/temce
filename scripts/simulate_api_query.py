# scripts/simulate_api_query.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.quote import QuoteModel
from models.instrument import InstrumentModel

DATABASE_URL = "sqlite+aiosqlite:///data/market.db"

async def simulate():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        instrument_id = "inst_f2d6ced51130"
        
        # 1. کوئری ساده بدون شرط اضافی (همان چیزی که API باید بزند)
        stmt = select(QuoteModel).where(QuoteModel.instrument_id == instrument_id).order_by(QuoteModel.created_at.desc()).limit(1)
        result = (await session.execute(stmt)).scalar_one_or_none()
        
        if result:
            print(f"✅ کوئری ساده موفق: {result.price_close}")
        else:
            print("❌ کوئری ساده هیچ نتیجه‌ای نداد.")
        
        # 2. تست با شرط `timeframe='1d'` (اگر API از آن استفاده کند)
        stmt2 = select(QuoteModel).where(QuoteModel.instrument_id == instrument_id).where(QuoteModel.timeframe == '1d').order_by(QuoteModel.created_at.desc()).limit(1)
        result2 = (await session.execute(stmt2)).scalar_one_or_none()
        if result2:
            print(f"✅ با شرط timeframe: {result2.price_close}")
        else:
            print("❌ با شرط timeframe نتیجه‌ای نداد.")
        
        # 3. تست با شرط `data_source='tsetmc'`
        stmt3 = select(QuoteModel).where(QuoteModel.instrument_id == instrument_id).where(QuoteModel.data_source == 'tsetmc').order_by(QuoteModel.created_at.desc()).limit(1)
        result3 = (await session.execute(stmt3)).scalar_one_or_none()
        if result3:
            print(f"✅ با شرط data_source: {result3.price_close}")
        else:
            print("❌ با شرط data_source نتیجه‌ای نداد.")

if __name__ == "__main__":
    asyncio.run(simulate())