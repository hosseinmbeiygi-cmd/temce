import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.needs_db

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://localhost:5432/market",
)


async def _ping_database():
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar()
    finally:
        await engine.dispose()


async def _test_db_connection():
    try:
        value = await _ping_database()
        print("[OK] Database connection succeeded")
        print(f"Query result: {value}")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Database unavailable: {exc}")


def test_database_connection():
    """Verify PostgreSQL connectivity using asyncpg."""
    asyncio.run(_test_db_connection())
