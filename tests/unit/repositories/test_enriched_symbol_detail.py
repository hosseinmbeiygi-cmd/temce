"""`get_enriched_symbol_detail` must not require the symbol to be the global latest.

A previous change filtered the snapshot row by ``fetched_at == MAX(fetched_at)``
across the whole table. With one fresher symbol, every other symbol returned
``None``. This test inserts exactly that shape and expects the symbol's own
latest row.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import BigInteger, DateTime, Float, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from brsapi.models.tsetmc import SymbolDetailModel, SymbolSnapshotModel
from brsapi.services.query_service import BrsApiQueryService


def _sqlite_type(column) -> str:
    col_type = column.type
    if isinstance(col_type, JSONB):
        return "TEXT"
    if isinstance(col_type, (BigInteger, Integer)):
        return "INTEGER"
    if isinstance(col_type, Float):
        return "REAL"
    if isinstance(col_type, DateTime):
        return "DATETIME"
    if isinstance(col_type, String):
        return "TEXT"
    return "TEXT"


def _detail_table_ddl() -> str:
    # SymbolDetailModel contains JSONB, which SQLite cannot create through the
    # ORM metadata; map JSONB to TEXT for this test-only table.
    columns = []
    for col in SymbolDetailModel.__table__.columns:
        ddl = f'"{col.name}" {_sqlite_type(col)}'
        if col.primary_key:
            ddl += " PRIMARY KEY"
        elif not col.nullable:
            ddl += " NOT NULL"
        columns.append(ddl)
    return f"CREATE TABLE brsapi_symbol_details ({', '.join(columns)})"


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SymbolSnapshotModel.__table__.create)
        await conn.execute(text(_detail_table_ddl()))
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        s.add_all(
            [
                SymbolSnapshotModel(
                    id=1,
                    ins_id="1",
                    symbol="A",
                    fetched_at=datetime(2026, 10, 28, 9, 0),
                    price_last=10.0,
                    created_at=datetime(2026, 10, 28, 9, 0),
                ),
                SymbolSnapshotModel(
                    id=2,
                    ins_id="1",
                    symbol="A",
                    fetched_at=datetime(2026, 10, 28, 9, 30),
                    price_last=11.0,
                    created_at=datetime(2026, 10, 28, 9, 30),
                ),
                # Fresher symbol; the old global-MAX filter made A return None.
                SymbolSnapshotModel(
                    id=3,
                    ins_id="2",
                    symbol="B",
                    fetched_at=datetime(2026, 10, 28, 9, 45),
                    price_last=20.0,
                    created_at=datetime(2026, 10, 28, 9, 45),
                ),
            ]
        )
        await s.commit()
        yield s
    await engine.dispose()


async def test_uses_this_symbols_latest_row_not_global_max(session: AsyncSession) -> None:
    row = await BrsApiQueryService(session).get_enriched_symbol_detail("A")

    assert row is not None
    assert row["symbol"] == "A"
    assert row["id"] == 2
    assert row["price_last"] == 11.0
