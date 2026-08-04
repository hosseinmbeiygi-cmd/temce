from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


class DatabaseConnection:
    def __init__(self, url: str | None = None, pool_size: int | None = None, max_overflow: int | None = None) -> None:
        self.url = url or settings.database_url_async
        # Defaults come from core settings (single source of truth), so the
        # pool size stays consistent across the codebase.
        self.pool_size = pool_size if pool_size is not None else settings.database_pool_size
        self.max_overflow = max_overflow if max_overflow is not None else settings.database_max_overflow
        self._engine: Any = None
        self._session_factory: Any = None

    async def initialize(self) -> None:
        if not HAS_SQLALCHEMY:
            logger.warning("SQLAlchemy not installed; database unavailable")
            return
        if self._engine is None:
            self._engine = create_async_engine(
                self.url,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                poolclass=NullPool if "sqlite" in self.url else None,
                echo=settings.database_echo,
            )
            self._session_factory = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
            logger.info("Database connection initialized: %s", self.url)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Any]:
        if not self._session_factory:
            await self.initialize()
        if self._session_factory:
            async with self._session_factory() as sess:
                yield sess
        else:
            yield None

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connection closed")
