from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

engine: Any = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_pool_config():
    is_sqlite = settings.database_url.startswith("sqlite")
    if is_sqlite:
        from sqlalchemy import NullPool

        return {"poolclass": NullPool}
    return {
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }


async def init_database() -> None:
    global engine, async_session_factory
    if engine is not None:
        return

    url = settings.database_url_async
    engine = create_async_engine(url, echo=settings.database_echo, **_get_pool_config())
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def close_database() -> None:
    global engine, async_session_factory
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_factory = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        await init_database()
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_session_blocking() -> AsyncSession:
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return async_session_factory()
