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

    # Try primary database (PostgreSQL); provide helpful error if unreachable
    if is_sqlite:
        logger.error(
            "Database is set to SQLite. "
            "This should be changed to PostgreSQL by editing the .env file or "
            "overriding the database_url setting. "
            "Set the DATABASE_URL in your .env file (e.g. postgresql+asyncpg://user:pass@localhost:5432/dbname) "
            "in your .env file to use PostgreSQL."
        )
        raise RuntimeError(
            "SQLite cannot be used. Set the DATABASE_URL in your .env file (e.g. postgresql+asyncpg://user:pass@localhost:5432/dbname) "
            "in your .env file. Note: PostgreSQL must be running on localhost:5432."
        )

    # Try to connect to PostgreSQL; no fallback for production
    if not is_sqlite:
        connected = await _try_connect(url)
        if not connected:
            logger.error(
                "Could not connect to PostgreSQL database at %s. "
                "Please ensure PostgreSQL is running on localhost:5432. "
                "Check DATABASE_URL in your .env file for the correct PostgreSQL connection string.",
                url.split("@")[-1] if "@" in url else url,
            )
            raise RuntimeError(
                "Cannot connect to PostgreSQL database. "
                "Please ensure PostgreSQL is running on the host and port specified in your .env DATABASE_URL. "
                f"Tried: {url}"
            )

    engine = create_async_engine(url, echo=settings.database_echo, **_get_pool_config(url))
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    # Auto-create tables only when explicitly enabled (SQLite dev mode).
    # Production uses Alembic migrations — running ``create_all`` on
    # PostgreSQL would race with (and bypass) the migration history.
    if settings.database_auto_create_tables:
        await _create_all_tables()
        logger.info("Auto-created tables (database_auto_create_tables=True)")

    logger.info("Database connected: %s", url.split("@")[-1] if "@" in url else url)


async def close_database() -> None:
    global engine, async_session_factory
    if engine is not None:
        try:
            await engine.dispose()
        except Exception:
            pass
        finally:
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
