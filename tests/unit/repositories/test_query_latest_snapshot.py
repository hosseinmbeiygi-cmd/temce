"""Latest-snapshot selection must follow ``fetched_at``, not insertion id.

A late/backfilled row is inserted later (higher ``id``/``created_at``) but
carries an older market timestamp. These tests insert exactly that shape and
assert the query layer keeps the row with the greatest ``fetched_at``.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from brsapi.models.tsetmc import SymbolSnapshotModel
from brsapi.services.query_service import BrsApiQueryService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SymbolSnapshotModel.__table__.create)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        # id=5 is the newest insertion but the oldest market timestamp.
        s.add_all(
            [
                SymbolSnapshotModel(id=1, ins_id="1", symbol="A", fetched_at=datetime(2026, 10, 28, 9, 30), price_last=10.0, trade_value=100.0, created_at=datetime(2026, 10, 28, 10, 0)),
                SymbolSnapshotModel(id=2, ins_id="1", symbol="A", fetched_at=datetime(2026, 10, 28, 9, 0), price_last=20.0, trade_value=100.0, created_at=datetime(2026, 10, 28, 10, 1)),
                SymbolSnapshotModel(id=3, ins_id="2", symbol="B", fetched_at=datetime(2026, 10, 28, 9, 30), price_last=30.0, trade_value=300.0, created_at=datetime(2026, 10, 28, 10, 2)),
                SymbolSnapshotModel(id=5, ins_id="1", symbol="A", fetched_at=datetime(2026, 10, 28, 8, 0), price_last=50.0, trade_value=100.0, created_at=datetime(2026, 10, 28, 10, 10)),
            ]
        )
        await s.commit()
        yield s
    await engine.dispose()


async def test_get_symbol_snapshot_uses_fetched_at_not_created_at(session: AsyncSession) -> None:
    row = await BrsApiQueryService(session).get_symbol_snapshot("A")

    assert row is not None
    assert row["id"] == 1  # greatest fetched_at (9:30); id=5 is newer by insertion only
    assert row["price_last"] == 10.0


async def test_get_latest_snapshots_ignores_late_backfill(session: AsyncSession) -> None:
    rows = await BrsApiQueryService(session).get_latest_snapshots(limit=10)

    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["A"]["id"] == 1
    assert by_symbol["B"]["id"] == 3
    assert all(row["id"] != 5 for row in rows)
