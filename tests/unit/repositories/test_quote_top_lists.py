"""Top gainers/losers/active must describe one trade date, one row per symbol.

Audit API-01. The three queries ranked the *entire* ``quotes`` history, so a
+300% session from months ago permanently held a slot in "today's gainers",
duplicate snapshots of the same symbol could occupy several slots, and the sort
scanned the whole table with no date predicate.

Rules locked here:
  * only rows whose ``date`` equals ``MAX(date)`` are candidates,
  * one row per symbol — the later ``time`` on that date wins,
  * ``limit`` is applied after both filters.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.quote import QuoteModel
from repositories.quote_repository import QuoteRepository


def _quote(
    id: str,
    instrument_id: str,
    symbol: str,
    date: str,
    time: str,
    change_pct: float,
    value: float,
    created_at: datetime | None = None,
) -> QuoteModel:
    return QuoteModel(
        id=id,
        instrument_id=instrument_id,
        symbol=symbol,
        date=date,
        time=time,
        price_change_pct=change_pct,
        value=value,
        # ``time`` is stored in mixed formats, so the repository orders
        # snapshots by ingestion time; make that order explicit here.
        created_at=created_at or datetime(2026, 10, 29, 12, 0),
    )


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(QuoteModel.__table__.create)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as s:
        s.add_all(
            [
                # Previous session with an extreme move: must never surface.
                _quote("old1", "i1", "AAA", "2026-10-28", "12:00", 300.0, 1.0),
                # Two snapshots of the same symbol on the latest date; the one
                # ingested later (value 20 / pct 2.5) is the current one.
                _quote(
                    "a1", "i1", "AAA", "2026-10-29", "09:00", 2.0, 10.0,
                    created_at=datetime(2026, 10, 29, 9, 1),
                ),
                _quote(
                    "a2", "i1", "AAA", "2026-10-29", "12:30", 2.5, 20.0,
                    created_at=datetime(2026, 10, 29, 12, 31),
                ),
                _quote("b1", "i2", "BBB", "2026-10-29", "12:30", 5.0, 50.0),
                _quote("c1", "i3", "CCC", "2026-10-29", "12:30", -3.0, 30.0),
            ]
        )
        await s.commit()
        yield s
    await engine.dispose()


async def test_top_gainers_use_only_the_latest_trade_date(session: AsyncSession) -> None:
    result = await QuoteRepository(session).get_top_gainers(limit=10)

    assert result.success
    rows = result.value
    # Ranked by change regardless of sign (pre-existing behaviour, unchanged);
    # the point is that the 2026-10-28 +300% row is gone.
    assert [q.symbol for q in rows] == ["BBB", "AAA", "CCC"]
    assert [q.price_change_pct for q in rows] == [5.0, 2.5, -3.0]
    assert all(q.date == "2026-10-29" for q in rows)


async def test_top_gainers_keep_one_row_per_symbol(session: AsyncSession) -> None:
    result = await QuoteRepository(session).get_top_gainers(limit=10)

    symbols = [q.symbol for q in result.value]
    assert len(symbols) == len(set(symbols))
    # The later snapshot (2.5 at 12:30), not the 09:00 one (2.0).
    aaa = next(q for q in result.value if q.symbol == "AAA")
    assert aaa.price_change_pct == 2.5


async def test_top_losers_use_the_same_filter(session: AsyncSession) -> None:
    result = await QuoteRepository(session).get_top_losers(limit=10)

    assert [q.symbol for q in result.value] == ["CCC", "AAA", "BBB"]
    assert all(q.date == "2026-10-29" for q in result.value)


async def test_most_active_uses_the_same_filter(session: AsyncSession) -> None:
    result = await QuoteRepository(session).get_most_active(limit=10)

    assert [q.symbol for q in result.value] == ["BBB", "CCC", "AAA"]
    assert [q.value for q in result.value] == [50.0, 30.0, 20.0]


async def test_limit_applies_after_filtering(session: AsyncSession) -> None:
    result = await QuoteRepository(session).get_top_gainers(limit=1)

    assert [q.symbol for q in result.value] == ["BBB"]
