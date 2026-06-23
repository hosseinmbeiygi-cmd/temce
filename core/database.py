from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

engine: Any = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None

SQLITE_FALLBACK_URL = "sqlite+aiosqlite:///data/market.db"


def _get_pool_config(url: str | None = None) -> dict[str, Any]:
    use_url = url or settings.database_url
    is_sqlite = use_url.startswith("sqlite")
    if is_sqlite:
        from sqlalchemy import NullPool

        return {"poolclass": NullPool}
    return {
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }


async def _try_connect(url: str) -> bool:
    """Try connecting to the given database URL. Returns True if successful."""
    tmp_engine = create_async_engine(url, echo=False, **_get_pool_config(url))
    try:
        async with tmp_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        await tmp_engine.dispose()
        return True
    except Exception:
        await tmp_engine.dispose()
        return False


async def _create_all_tables() -> None:
    """Import all models and create tables (used for SQLite fallback)."""
    import models  # noqa: F401 — triggers registration of all model classes
    from models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("SQLite tables created")


async def init_database() -> None:
    global engine, async_session_factory
    if engine is not None:
        return

    # Ensure data directory exists for SQLite fallback
    Path("data").mkdir(parents=True, exist_ok=True)

    url = settings.database_url_async
    is_sqlite = url.startswith("sqlite")

    # Try primary database; fallback to SQLite if unreachable
    if not is_sqlite:
        connected = await _try_connect(url)
        if not connected:
            logger.warning(
                "Primary database unreachable at %s — falling back to SQLite: %s",
                url.split("@")[-1] if "@" in url else url,
                SQLITE_FALLBACK_URL,
            )
            url = SQLITE_FALLBACK_URL
            is_sqlite = True

    engine = create_async_engine(url, echo=settings.database_echo, **_get_pool_config(url))
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    # Auto-create tables when using SQLite so endpoints don't 500
    if is_sqlite:
        await _create_all_tables()

    logger.info("Database connected: %s", url.split("@")[-1] if "@" in url else url)


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
