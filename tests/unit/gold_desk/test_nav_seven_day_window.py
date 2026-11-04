"""The 7-day NAV change must compare two *different* NAV dates.

Audit FIN-07. ``_nav_7d_ago`` filtered only ``date <= today-7``; a fund whose
single NAV row was older than the cutoff matched that same row, so ``nav`` and
``nav_7d`` were identical and the scorer received a neutral 0.0% instead of
"no data".
"""

from __future__ import annotations

import jdatetime
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from brsapi.models import NavRecordModel
from core.time import now_tehran
from src.gold_desk.nav_checker import _nav_7d_ago


def _jalali_days_ago(days: int) -> str:
    today = jdatetime.date.fromgregorian(date=now_tehran().date())
    return (today - jdatetime.timedelta(days=days)).strftime("%Y-%m-%d")


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(NavRecordModel.__table__.create)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _row(row_id: int, symbol: str, days_ago: int, nav: float) -> NavRecordModel:
    return NavRecordModel(
        id=row_id,
        symbol=symbol,
        date=_jalali_days_ago(days_ago),
        nav_issue=nav,
        nav_redemption=nav,
    )


async def test_returns_a_strictly_older_nav(session) -> None:
    session.add_all([_row(1, "FUND", 10, 100.0), _row(2, "FUND", 0, 110.0)])
    await session.flush()

    assert await _nav_7d_ago(session, "FUND") == 100.0


async def test_single_stale_row_is_not_compared_with_itself(session) -> None:
    session.add(_row(1, "FUND", 30, 100.0))
    await session.flush()

    assert await _nav_7d_ago(session, "FUND") is None


async def test_a_row_inside_the_window_is_not_used(session) -> None:
    session.add_all([_row(1, "FUND", 5, 100.0), _row(2, "FUND", 0, 110.0)])
    await session.flush()

    assert await _nav_7d_ago(session, "FUND") is None


async def test_other_symbols_do_not_leak(session) -> None:
    session.add_all([_row(1, "OTHER", 10, 50.0), _row(2, "FUND", 0, 110.0)])
    await session.flush()

    assert await _nav_7d_ago(session, "FUND") is None
