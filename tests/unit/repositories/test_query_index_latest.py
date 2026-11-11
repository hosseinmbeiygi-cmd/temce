"""Latest index selection must use source time, not insertion time."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from brsapi.models.tsetmc import IndexValueModel
from brsapi.services.query_service import BrsApiQueryService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(IndexValueModel.__table__.create)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        s.add_all(
            [
                # id=1 is inserted last (created_at newest) but its source time is older.
                IndexValueModel(
                    id=1,
                    name="شاخص کل",
                    index_value=100.0,
                    fetched_at=datetime(2026, 10, 28, 9, 0),
                    created_at=datetime(2026, 10, 28, 12, 0),
                ),
                IndexValueModel(
                    id=2,
                    name="شاخص کل",
                    index_value=200.0,
                    fetched_at=datetime(2026, 10, 28, 11, 0),
                    created_at=datetime(2026, 10, 28, 11, 0),
                ),
                IndexValueModel(
                    id=3,
                    name="شاخص هم‌وزن",
                    index_value=300.0,
                    fetched_at=datetime(2026, 10, 28, 11, 0),
                    created_at=datetime(2026, 10, 28, 11, 0),
                ),
            ]
        )
        await s.commit()
        yield s
    await engine.dispose()


async def test_latest_indices_uses_fetched_at(session: AsyncSession) -> None:
    rows = await BrsApiQueryService(session).get_latest_indices()

    by_name = {row["name"]: row for row in rows}
    assert by_name["شاخص کل"]["id"] == 2
    assert by_name["شاخص کل"]["index_value"] == 200.0
    assert by_name["شاخص هم‌وزن"]["id"] == 3


async def test_index_history_orders_by_source_time(session: AsyncSession) -> None:
    rows = await BrsApiQueryService(session).get_index_history("شاخص کل")

    assert [row["id"] for row in rows] == [2, 1]
