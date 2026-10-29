"""Watchlists are per-user data: no shared list, no cross-user delete.

Audit SEC-04. The ``watchlist`` table had no ``user_id`` and ``symbol`` was
globally UNIQUE, so every account shared one list and any account could delete
another's symbols.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.watchlist_service import WatchlistService


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # Mirrors the shape `_ensure_table` creates on PostgreSQL, in SQLite
        # syntax (SERIAL is not valid there).
        await conn.execute(
            text(
                """
                CREATE TABLE watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol VARCHAR(50) NOT NULL,
                    name VARCHAR(200) DEFAULT '',
                    note TEXT DEFAULT '',
                    sort_order INTEGER DEFAULT 0,
                    user_id VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, symbol)
                )
                """
            )
        )
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _symbols(svc: WatchlistService, user_id: str) -> list[str]:
    result = await svc.list_items(user_id=user_id)
    assert result.success
    return [row["symbol"] for row in result.value]


async def test_two_users_can_watch_the_same_symbol(session: AsyncSession) -> None:
    svc = WatchlistService(session)

    first = await svc.add_symbol("فولاد", user_id="user-1")
    second = await svc.add_symbol("فولاد", user_id="user-2")

    assert first.success, first.error
    assert second.success, second.error
    assert await _symbols(svc, "user-1") == ["فولاد"]
    assert await _symbols(svc, "user-2") == ["فولاد"]


async def test_lists_do_not_leak_between_users(session: AsyncSession) -> None:
    svc = WatchlistService(session)
    await svc.add_symbol("فولاد", user_id="user-1")
    await svc.add_symbol("شپنا", user_id="user-2")

    assert await _symbols(svc, "user-1") == ["فولاد"]
    assert await _symbols(svc, "user-2") == ["شپنا"]


async def test_duplicate_within_one_list_is_rejected(session: AsyncSession) -> None:
    svc = WatchlistService(session)
    await svc.add_symbol("فولاد", user_id="user-1")

    again = await svc.add_symbol("فولاد", user_id="user-1")
    assert not again.success

    other = await svc.add_symbol("فولاد", user_id="user-2")
    assert other.success


async def test_remove_only_touches_the_callers_list(session: AsyncSession) -> None:
    svc = WatchlistService(session)
    await svc.add_symbol("فولاد", user_id="user-1")
    await svc.add_symbol("فولاد", user_id="user-2")

    removed = await svc.remove_symbol("فولاد", user_id="user-2")
    assert removed.success
    assert await _symbols(svc, "user-2") == []
    assert await _symbols(svc, "user-1") == ["فولاد"]


async def test_sort_order_is_per_user(session: AsyncSession) -> None:
    svc = WatchlistService(session)
    await svc.add_symbol("فولاد", user_id="user-1")
    await svc.add_symbol("شپنا", user_id="user-2")

    second = await svc.add_symbol("خودرو", user_id="user-2")

    assert second.success
    assert second.value["order"] == 2
