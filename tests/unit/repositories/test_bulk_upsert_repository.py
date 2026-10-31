"""Persistence-contract tests for ``BulkUpsertRepository`` on SQLite.

These tests do not need PostgreSQL: the repository issues portable SQL
(``INSERT ... ON CONFLICT (...) DO UPDATE`` / ``DO NOTHING`` and a scoped
``DELETE``) that SQLite understands. They pin down:

* idempotency of the ``(symbol, fetched_at)`` upsert,
* the meaning of the returned counter (rows actually affected), and
* the scope of ``delete_where`` (only the requested slice is removed).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from brsapi.models.tsetmc import SymbolSnapshotModel
from brsapi.repositories.base import BulkUpsertRepository

TABLE_DDL = """
CREATE TABLE brsapi_symbol_snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT NOT NULL,
    fetched_at DATETIME,
    price_last FLOAT,
    UNIQUE (symbol, fetched_at)
)
"""


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text(TABLE_DDL))
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _count(session: AsyncSession) -> int:
    return (await session.execute(text("SELECT COUNT(*) FROM brsapi_symbol_snapshots"))).scalar_one()


async def test_upsert_is_idempotent_and_refreshes_on_conflict(session: AsyncSession) -> None:
    repo = BulkUpsertRepository(session, SymbolSnapshotModel)
    fetched_at = datetime(2026, 10, 28, 9, 30, 0)
    first = [{"symbol": "A", "fetched_at": fetched_at, "price_last": 100.0}]

    assert await repo.bulk_insert(first, on_conflict_update=True, conflict_target=["symbol", "fetched_at"]) == 1
    # Same natural key, newer value: must update, not append.
    second = [{"symbol": "A", "fetched_at": fetched_at, "price_last": 125.0}]
    assert await repo.bulk_insert(second, on_conflict_update=True, conflict_target=["symbol", "fetched_at"]) == 1

    assert await _count(session) == 1
    price = (await session.execute(text("SELECT price_last FROM brsapi_symbol_snapshots"))).scalar_one()
    assert price == 125.0


async def test_plain_insert_counter_reports_affected_rows(session: AsyncSession) -> None:
    """``ON CONFLICT DO NOTHING`` reports 0 for a skipped duplicate."""
    repo = BulkUpsertRepository(session, SymbolSnapshotModel)
    fetched_at = datetime(2026, 10, 28, 9, 30, 0)
    row = [{"symbol": "A", "fetched_at": fetched_at, "price_last": 100.0}]

    assert await repo.bulk_insert(row) == 1
    assert await repo.bulk_insert(row) == 0
    assert await _count(session) == 1


async def test_upsert_deduplicates_duplicate_conflict_keys_in_one_batch(session: AsyncSession) -> None:
    repo = BulkUpsertRepository(session, SymbolSnapshotModel)
    fetched_at = datetime(2026, 10, 28, 9, 30, 0)
    rows = [
        {"symbol": "A", "fetched_at": fetched_at, "price_last": 100.0},
        {"symbol": "A", "fetched_at": fetched_at, "price_last": 125.0},
    ]

    assert await repo.bulk_insert(rows, on_conflict_update=True, conflict_target=["symbol", "fetched_at"]) == 1
    assert await _count(session) == 1
    price = (await session.execute(text("SELECT price_last FROM brsapi_symbol_snapshots"))).scalar_one()
    assert price == 125.0


async def test_delete_where_only_removes_the_requested_slice(session: AsyncSession) -> None:
    repo = BulkUpsertRepository(session, SymbolSnapshotModel)
    await repo.bulk_insert(
        [
            {"symbol": "A", "fetched_at": datetime(2026, 10, 28, 9, 0, 0), "price_last": 1.0},
            {"symbol": "A", "fetched_at": datetime(2026, 10, 28, 9, 5, 0), "price_last": 2.0},
            {"symbol": "B", "fetched_at": datetime(2026, 10, 28, 9, 0, 0), "price_last": 3.0},
        ]
    )

    deleted = await repo.delete_where("symbol", "A")

    assert deleted == 2
    assert await _count(session) == 1
    remaining = (await session.execute(text("SELECT symbol FROM brsapi_symbol_snapshots"))).scalar_one()
    assert remaining == "B"


async def test_truncate_requires_explicit_environment_opt_in(session: AsyncSession, monkeypatch) -> None:
    monkeypatch.delenv("ALLOW_TABLE_TRUNCATE", raising=False)
    repo = BulkUpsertRepository(session, SymbolSnapshotModel)

    with pytest.raises(RuntimeError, match="ALLOW_TABLE_TRUNCATE"):
        await repo.truncate()


async def test_delete_where_rejects_unknown_columns(session: AsyncSession) -> None:
    repo = BulkUpsertRepository(session, SymbolSnapshotModel)
    with pytest.raises(ValueError, match="Invalid SQL identifier|Unknown column"):
        await repo.delete_where("symbol; DROP TABLE users; --", "A")
