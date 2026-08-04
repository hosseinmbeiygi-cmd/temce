import asyncio
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from services.quote_service import QuoteService

pytestmark = pytest.mark.needs_db

# scripts/test_dependencies.py

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_dependency():
    # 1. شبیه‌سازی کاری که get_quote_service در dependencies.py انجام می‌دهد
    # (فرض می‌کنیم که از get_db_session استفاده می‌کند)
    # ما خودمان یک session از settings.database_url می‌سازیم
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        service = QuoteService(session=session)
        result = await service.get_latest("inst_f2d6ced51130")
        if result.success:
            print(f"✅ داده پیدا شد: {result.value.price_close}")
        else:
            print(f"❌ خطا: {result.error}")


if __name__ == "__main__":
    asyncio.run(test_dependency())
