"""Timestamps must be naive UTC, not host-local time.

The host clock is UTC+03:30, while retention/stats compare against
``core.time.utc_now_naive()``. These tests fail on a host-offset clock if the
repositories accidentally write ``datetime.now()`` (local) again.
"""

from __future__ import annotations

from datetime import datetime

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from brsapi.models.base import SyncLogModel
from brsapi.repositories.base import RawPayloadRepository, SyncLogRepository
from core.time import utc_now_naive

SYNC_LOG_DDL = """
CREATE TABLE brsapi_sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint        VARCHAR(100) NOT NULL,
    category        VARCHAR(30)  NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'success',
    outcome         VARCHAR(30)  NOT NULL DEFAULT 'unknown',
    items_count     INTEGER      NOT NULL DEFAULT 0,
    error_message   TEXT,
    duration_ms     FLOAT        NOT NULL DEFAULT 0.0,
    params_snapshot TEXT,
    started_at      DATETIME     NOT NULL,
    completed_at    DATETIME
)
"""


class FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text(SYNC_LOG_DDL))
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_raw_payload_fetched_at_is_naive_utc() -> None:
    repo = RawPayloadRepository(FakeSession())  # type: ignore[arg-type]

    entry = await repo.store(endpoint="/Test", payload="{}")

    assert entry.fetched_at == entry.receive_time
    skew = (utc_now_naive() - entry.fetched_at).total_seconds()
    # A local-time write on a UTC+03:30 host yields ~-12600s.
    assert 0 <= skew < 60


async def test_sync_log_started_at_is_naive_utc(session: AsyncSession) -> None:
    repo = SyncLogRepository(session)

    entry = await repo.record(endpoint="/Test", category="test")

    assert entry.started_at is not None
    skew = (utc_now_naive() - entry.started_at).total_seconds()
    assert 0 <= skew < 60
    assert isinstance(entry.started_at, datetime)
    assert isinstance(entry, SyncLogModel)
