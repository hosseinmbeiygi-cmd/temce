"""Regression tests for critical BrsApi sync bugs found in production logs.

1. ``BulkUpsertRepository.bulk_insert(on_conflict_update=True)`` generated
   ``ON CONFLICT DO UPDATE`` **without a conflict target**, which is a syntax
   error in PostgreSQL → ``brsapi_all_symbols`` FAILed every 2 minutes.

2. ``TsetmcParser.parse_index`` wrote a **string** into the ``DateTime``
   ``fetched_at`` column of ``brsapi_index_values`` → asyncpg ``DataError`` →
   ``brsapi_index`` FAILed every 2 minutes.

3. ``TsetmcParser.parse_all_symbols`` wrote a **string** into the ``DateTime``
   ``fetched_at`` column of ``brsapi_symbol_snapshots`` (masked by the
   ON CONFLICT syntax error; surfaced once that was fixed).
   ``SymbolSnapshotModel.fetched_at`` is now ``DateTime`` matching the live DB.

4. Dead ``nabzebourse.com`` RSS feeds (HTTP 404) were removed from the news
   config to stop the wasted retries each news cycle.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import DateTime

from brsapi.models import IndexValueModel, SymbolSnapshotModel
from brsapi.parsers import TsetmcParser
from brsapi.repositories import BulkUpsertRepository


# ── Bug 1: ON CONFLICT DO UPDATE without a conflict target ──────────────


async def test_bulk_insert_on_conflict_update_requires_conflict_target():
    """DO UPDATE without a target is a Postgres syntax error — must refuse loudly."""
    repo = BulkUpsertRepository(AsyncMock(), SymbolSnapshotModel)
    with pytest.raises(ValueError, match="conflict_target"):
        await repo.bulk_insert(
            [{"symbol": "X", "fetched_at": "2026-01-01 00:00:00"}],
            on_conflict_update=True,
        )


async def test_bulk_insert_conflict_target_generates_valid_sql():
    """Generated SQL must carry the (symbol, fetched_at) inference target."""
    session = AsyncMock()
    repo = BulkUpsertRepository(session, SymbolSnapshotModel)
    records = [{"symbol": "X", "price_last": 100.0, "fetched_at": "2026-01-01 00:00:00"}]
    await repo.bulk_insert(
        records,
        on_conflict_update=True,
        conflict_target=["symbol", "fetched_at"],
    )
    sql = str(session.execute.call_args.args[0])
    assert 'ON CONFLICT ("symbol", "fetched_at") DO UPDATE SET' in sql
    assert '"price_last" = EXCLUDED."price_last"' in sql


async def test_bulk_insert_conflict_update_never_touches_pk():
    """The autoincrement ``id`` PK must never be overwritten on conflict."""
    session = AsyncMock()
    repo = BulkUpsertRepository(session, SymbolSnapshotModel)
    records = [{"id": 999, "symbol": "X", "fetched_at": "2026-01-01 00:00:00"}]
    await repo.bulk_insert(
        records,
        on_conflict_update=True,
        conflict_target=["symbol", "fetched_at"],
    )
    sql = str(session.execute.call_args.args[0])
    assert '"id" = EXCLUDED."id"' not in sql


async def test_bulk_insert_default_still_do_nothing():
    """Plain inserts keep the safe ``ON CONFLICT DO NOTHING`` (no target needed)."""
    session = AsyncMock()
    repo = BulkUpsertRepository(session, SymbolSnapshotModel)
    await repo.bulk_insert([{"symbol": "X", "fetched_at": "2026-01-01 00:00:00"}])
    sql = str(session.execute.call_args.args[0])
    assert "ON CONFLICT DO NOTHING" in sql


# ── Bug 2: string bound into a DateTime column (brsapi_index_values) ────


def test_parse_index_fetched_at_is_datetime():
    """parse_index must emit a real datetime (asyncpg rejects str for DateTime)."""
    records = TsetmcParser.parse_index([{"index": 5154057.38, "date": "1405-05-11"}])
    assert len(records) == 1
    assert isinstance(records[0]["fetched_at"], datetime)


def test_parse_index_handles_single_dict_and_list():
    """The API returns a dict (type=1/2) or a list (type=3) — both must work."""
    single = TsetmcParser.parse_index({"index": 1.0})
    assert len(single) == 1
    assert isinstance(single[0]["fetched_at"], datetime)
    many = TsetmcParser.parse_index([{"index": 1.0}, {"index": 2.0}])
    assert len(many) == 2


def test_index_model_fetched_at_column_is_datetime():
    """Model must match the live DB column (created as DateTime by migration 001)."""
    col = IndexValueModel.__table__.c.fetched_at
    assert isinstance(col.type, DateTime)


def test_symbol_snapshot_fetched_at_column_is_datetime():
    """Live DB brsapi_symbol_snapshots.fetched_at is timestamptz (migration 001).

    The old String(30) model + string parser output made the live sync fail with
    asyncpg DataError as soon as the ON CONFLICT syntax bug was fixed.
    """
    col = SymbolSnapshotModel.__table__.c.fetched_at
    assert isinstance(col.type, DateTime)


def test_parse_all_symbols_fetched_at_is_datetime():
    """parse_all_symbols must emit a real datetime (snapshot column is timestamptz)."""
    records = TsetmcParser.parse_all_symbols(
        [{"l18": "عیار", "l30": "صندوق", "id": "123", "time": "12:30:00"}]
    )
    assert len(records) == 1
    assert isinstance(records[0]["fetched_at"], datetime)
    # Second-truncated: keeps the (symbol, fetched_at) upsert dedup semantics.
    assert records[0]["fetched_at"].microsecond == 0


# ── Bug 3: dead nabzebourse RSS feeds removed ───────────────────────────


def test_no_dead_nabzebourse_feeds_in_domestic_provider():
    from providers.news.domestic.rss_domestic_provider import DOMESTIC_RSS_FEEDS

    assert DOMESTIC_RSS_FEEDS
    assert not any("nabzebourse" in url for url in DOMESTIC_RSS_FEEDS.values())


def test_no_nabzebourse_in_chat_news_fetcher():
    from services.chat.news_fetcher import NewsFetcher

    assert NewsFetcher.RSS_SOURCES
    assert not any("nabzebourse" in url for url in NewsFetcher.RSS_SOURCES.values())
