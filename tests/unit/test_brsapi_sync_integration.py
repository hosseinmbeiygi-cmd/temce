"""End-to-end integration test for the two critical BrsApi sync fixes.

Runs the **real** ``BrsApiSyncService`` pipeline (fetch → parse →
``bulk_insert`` → commit) against a real PostgreSQL instance, so we prove
the fixed SQL actually executes — not just that the string is built right:

1. ``sync_all_symbols`` must INSERT without the old
   ``ON CONFLICT DO UPDATE requires inference specification`` syntax error.
2. ``sync_index`` must INSERT without the old ``expected a datetime
   instance, got 'str'`` binding error (the ``fetched_at`` DateTime column).

A throwaway PostgreSQL schema (``test_brsapi_<uuid>``) is created and
dropped around the tests so live tables are never touched. All connections
from the fixture engine land in that schema via ``search_path``.

Requires the **asyncpg** driver (``DATABASE_URL`` with ``+asyncpg``): the
schema scoping relies on ``connect_args={"server_settings": {...}}`` which is
an asyncpg-only connection option. ``create_all`` is scoped to exactly the
four tables the pipeline touches (snapshots, index values, sync log, raw
payloads) so future brsapi models needing extensions can't break this test.

Skipped automatically when PostgreSQL is unreachable (``needs_db`` marker —
see ``tests/conftest.py``; the connectivity probe runs once per session at
collection time, so assertion failures inside these tests always surface as
real failures, never as skips). Run with a reachable ``DATABASE_URL``, e.g.::

    DATABASE_URL=$(grep '^DATABASE_URL=' .env | cut -d= -f2-) \\
        python -m pytest tests/unit/test_brsapi_sync_integration.py -v
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from brsapi.client import BrsApiResponse
from brsapi.models.base import BrsApiBase, RawPayloadModel, SyncLogModel
from brsapi.models.tsetmc import IndexValueModel, SymbolSnapshotModel
from brsapi.repositories import BulkUpsertRepository
from brsapi.services.sync_service import BrsApiSyncService
from core.result import Result

# Tables the pipeline writes: the two under test + the sync-log / raw-payload
# audit tables the generic ``sync()`` path records into.
_TABLES_UNDER_TEST = [
    SymbolSnapshotModel.__table__,
    IndexValueModel.__table__,
    SyncLogModel.__table__,
    RawPayloadModel.__table__,
]


# ── Canned BrsApi payloads (realistic field names) ─────────────────────

_SYMBOL_ITEM = {
    "id": "34144395039913458",
    "l18": "عیار",
    "l30": "صندوق طلای عیار مفید",
    "isin": "IRTKMOFD0001",
    "cs": "صندوق سرمایه\u200cگذاری قابل معامله",
    "cs_id": 68,
    "z": 4810000000,
    "bvol": 1,
    "mv": 2435096170000000.0,
    "eps": 0.0,
    "pe": 0.0,
    "pmin": 500010.0,
    "pmax": 509999.0,
    "py": 518652.0,
    "pf": 501999.0,
    "pl": 509470.0,
    "plc": -9182.0,
    "plp": -1.77,
    "pc": 506257.0,
    "pcc": -12395.0,
    "pcp": -2.39,
    "tno": 65170,
    "tvol": 63638090,
    "tval": 32217202986170.0,
    "Buy_CountI": 24688,
    "Buy_CountN": 64,
    "Sell_CountI": 10502,
    "Sell_CountN": 32,
    "Buy_I_Volume": 54304727,
    "Buy_N_Volume": 9333363,
    "Sell_I_Volume": 49888470,
    "Sell_N_Volume": 13749620,
    "time": "16:59:59",
}

_INDEX_ITEM = {
    "date": "1405-05-11",
    "time": "16:21:39",
    "state": "بسته",
    "index": 5154057.38,
    "index_change": 99270.72,
    "index_equalWeight": 1461308.08,
    "index_equalWeight_change": 21788.06,
    "mv": 1.4794401309890768e17,
    "tno": 564272,
    "tval": 320731590809773.0,
    "tvol": 52950966152,
}


class _FakeBrsApiClient:
    """No-network client returning canned payloads for the two endpoints."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def fetch(self, endpoint, params=None, category_override=None):
        self.calls.append(endpoint.path)
        if endpoint.path == "/Tsetmc/AllSymbols.php":
            data = [dict(_SYMBOL_ITEM)]
        elif endpoint.path == "/Tsetmc/Index.php":
            data = dict(_INDEX_ITEM)
        else:
            data = []
        return Result.ok(
            BrsApiResponse(endpoint=endpoint.path, status_code=200, data=data)
        )


# ── Fixture: throwaway Postgres schema ────────────────────────────────


def _db_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://market:market@localhost:5432/market_test",
    )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest.fixture()
async def brsapi_db():
    """Throwaway schema with only the BrsApi tables under test.

    Function-scoped: every test gets a fresh ``test_brsapi_<uuid>`` schema, so
    the three tests can't collide. All connections land in that schema via
    asyncpg ``server_settings.search_path`` — the service's unqualified
    INSERT/TRUNCATE statements therefore target the throwaway tables only and
    the live ``public`` tables are never touched.
    """
    schema = f"test_brsapi_{uuid.uuid4().hex[:10]}"
    base_url = _db_url()

    admin = create_async_engine(base_url)
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    finally:
        await admin.dispose()

    engine = create_async_engine(
        base_url,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            BrsApiBase.metadata.create_all, tables=_TABLES_UNDER_TEST
        )

    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield engine, Session
    finally:
        # Defensive teardown: dispose the scoped pool first, then drop the
        # schema from a fresh admin connection (IF EXISTS so a stale schema
        # from a crashed run can't error the next run).
        await engine.dispose()
        admin = create_async_engine(base_url)
        try:
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            await admin.dispose()


# ── Tests ─────────────────────────────────────────────────────────────


@pytest.mark.needs_db
async def test_sync_all_symbols_and_index_insert_against_real_db(brsapi_db):
    """Full service pipeline persists rows in real PostgreSQL without errors."""
    engine, Session = brsapi_db
    client = _FakeBrsApiClient()

    async with Session() as session:
        service = BrsApiSyncService(client=client, session=session)

        sym_report = await service.sync_all_symbols(session)
        assert sym_report.success, f"sync_all_symbols failed: {sym_report.error}"
        assert sym_report.items_count == 1

        idx_report = await service.sync_index(session, "1")
        assert idx_report.success, f"sync_index failed: {idx_report.error}"
        assert idx_report.items_count == 1

        # Rows are actually persisted inside the throwaway schema.
        sym_count = (
            await session.execute(select(func.count()).select_from(SymbolSnapshotModel))
        ).scalar()
        idx_count = (
            await session.execute(select(func.count()).select_from(IndexValueModel))
        ).scalar()
        assert sym_count == 1
        assert idx_count == 1

        # Both fetched_at columns must be DateTime — the live DB is timestamptz;
        # a String(30) model here would mask the parser's string-output bug.
        assert SymbolSnapshotModel.__table__.c.fetched_at.type.python_type is datetime
        assert IndexValueModel.__table__.c.fetched_at.type.python_type is datetime

        # The index row's fetched_at survived the DateTime column binding as a
        # real datetime (the pre-fix string would have raised a DataError).
        idx_row = (await session.execute(select(IndexValueModel))).scalars().first()
        assert isinstance(idx_row.fetched_at, datetime)

        # The snapshot symbol landed with its price.
        sym_row = (await session.execute(select(SymbolSnapshotModel))).scalars().first()
        assert sym_row.symbol == "عیار"
        assert sym_row.price_last == 509470.0

    assert "/Tsetmc/AllSymbols.php" in client.calls
    assert "/Tsetmc/Index.php" in client.calls


@pytest.mark.needs_db
async def test_bulk_insert_upsert_conflicts_on_real_pg(brsapi_db):
    """ON CONFLICT (symbol, fetched_at) DO UPDATE updates, never duplicates."""
    engine, Session = brsapi_db

    async with Session() as session:
        repo = BulkUpsertRepository(session, SymbolSnapshotModel)
        base = {
            "ins_id": "8175784894140974",
            "symbol": "فزر",
            "name": "پویا زرکان آق دره",
            "price_last": 175600.0,
            "time": "12:30:00",
            "fetched_at": datetime(2026, 8, 2, 19, 39, 31),
            "raw_json": "{}",
        }

        n1 = await repo.bulk_insert(
            [dict(base)],
            on_conflict_update=True,
            conflict_target=["symbol", "fetched_at"],
        )
        assert n1 == 1

        # Same (symbol, fetched_at) — the DO UPDATE path must refresh the row.
        updated = dict(base)
        updated["price_last"] = 179900.0
        n2 = await repo.bulk_insert(
            [updated],
            on_conflict_update=True,
            conflict_target=["symbol", "fetched_at"],
        )
        assert n2 == 1
        await session.commit()

        rows = (await session.execute(select(SymbolSnapshotModel))).scalars().all()
        assert len(rows) == 1, "conflict upsert created a duplicate row"
        assert rows[0].price_last == 179900.0
        assert rows[0].name == "پویا زرکان آق دره"


@pytest.mark.needs_db
async def test_bulk_insert_do_nothing_plain_insert_on_real_pg(brsapi_db):
    """Plain inserts (no conflict target) keep working on real PostgreSQL."""
    engine, Session = brsapi_db

    async with Session() as session:
        repo = BulkUpsertRepository(session, IndexValueModel)
        rec = {
            "name": "شاخص کل",
            "state": "بسته",
            "index_value": 5154057.38,
            "date": "1405-05-11",
            "time": "16:21:39",
            "fetched_at": datetime(2026, 8, 2, 19, 39, 32),
            "raw_json": "{}",
        }
        n = await repo.bulk_insert([rec])
        await session.commit()
        assert n == 1

        count = (
            await session.execute(select(func.count()).select_from(IndexValueModel))
        ).scalar()
        assert count == 1
