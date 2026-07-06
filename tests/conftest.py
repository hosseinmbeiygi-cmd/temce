from __future__ import annotations

import asyncio
import sys

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from core.database import _create_all_tables, async_session_factory, engine
import core.database as db

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture(scope="module")
async def db_engine(request):
    """Initialize database with a NullPool engine to avoid cross-loop pool issues."""
    from sqlalchemy import NullPool

    test_engine = create_async_engine(
        settings.database_url_async,
        echo=settings.database_echo,
        poolclass=NullPool,
    )
    test_session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False,
    )

    old_engine = db.engine
    old_factory = db.async_session_factory
    db.engine = test_engine
    db.async_session_factory = test_session_factory

    async with test_engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    await _create_all_tables()

    yield test_engine

    await test_engine.dispose()
    db.engine = old_engine
    db.async_session_factory = old_factory


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Provide a clean database session for each test."""
    async with db.async_session_factory() as session:
        yield session
        await session.rollback()
        await session.close()


@pytest.fixture(scope="module", autouse=True)
def _db_engine_auto(db_engine):
    """Ensure db_engine is initialized for every test module."""
    pass


@pytest.fixture
def sample_instrument_data():
    return {
        "id": "inst_test_001",
        "symbol": "فولاد",
        "name": "فولاد مبارکه اصفهان",
        "isin": "IRO1FOLD0001",
        "market_type": "bours",
        "asset_class": "equity",
    }


@pytest.fixture
def sample_quote_data():
    return {
        "id": "q_test_001",
        "instrument_id": "inst_test_001",
        "symbol": "فولاد",
        "price_close": 15000,
        "price_open": 14900,
        "price_high": 15100,
        "price_low": 14850,
        "volume": 5000000,
        "value": 75000000000,
        "date": "2024-01-15",
        "time": "12:30:00",
    }
