"""Shared fixtures for repository-level tests.

Provides an in-memory SQLite async session (``db_session``) so that
repository unit tests can run without a real PostgreSQL instance.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Return an in-memory SQLite session with ``brsapi_sync_log`` table.

    The table is created via raw DDL because SQLite + ``BigInteger``
    + ``autoincrement`` doesn't work well through the ORM metadata
    (``JSONB`` in other models also causes ``CompileError``).

    Each test function gets a fresh engine + session so there is
    no state leakage between tests.  The in-memory database is
    destroyed when the engine is disposed.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE brsapi_sync_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint        VARCHAR(100) NOT NULL,
                category        VARCHAR(30)  NOT NULL,
                status          VARCHAR(20)  NOT NULL DEFAULT 'success',
                items_count     INTEGER      NOT NULL DEFAULT 0,
                error_message   TEXT,
                duration_ms     FLOAT        NOT NULL DEFAULT 0.0,
                params_snapshot TEXT,
                started_at      DATETIME     NOT NULL,
                completed_at    DATETIME
            )
        """))
        await conn.execute(text("""
            CREATE INDEX idx_sync_log_endpoint_time
            ON brsapi_sync_log (endpoint, started_at)
        """))

    factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with factory() as session:
        yield session

    await engine.dispose()
