"""Unit tests for ``is_high_vol_window`` economic-calendar service.

Pure tests use recorded fixtures; no network or database required.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.gold.economic_calendar import (
    DEFAULT_HIGH_VOL_WINDOW_DAYS,
    add_iran_manual_event,
    is_high_vol_window,
    is_high_vol_window_from_events,
    list_economic_calendar,
    list_iran_manual_events,
)
from services.gold.macro_sync import HIGH_VOLATILITY_CATEGORIES

# ── Pure (fixture-based) tests ───────────────────────────────────────────

def _event(event_date: str, category: str = "CPI", is_high_volatility: bool | None = None) -> dict:
    ev = {"event_date": event_date, "category": category}
    if is_high_volatility is not None:
        ev["is_high_volatility"] = is_high_volatility
    return ev


def test_is_high_vol_window_true_on_event_date() -> None:
    events = [_event("2026-10-15", "CPI")]
    assert is_high_vol_window_from_events(date(2026, 10, 15), events) is True


def test_is_high_vol_window_true_within_window() -> None:
    events = [_event("2026-10-15", "CPI")]
    assert is_high_vol_window_from_events(date(2026, 10, 14), events) is True  # -1 day
    assert is_high_vol_window_from_events(date(2026, 10, 16), events) is True  # +1 day


def test_is_high_vol_window_false_outside_window() -> None:
    events = [_event("2026-10-15", "CPI")]
    assert is_high_vol_window_from_events(date(2026, 10, 13), events) is False  # -2 days
    assert is_high_vol_window_from_events(date(2026, 10, 17), events) is False  # +2 days


def test_is_high_vol_window_categories_cpi_nfp_fomc() -> None:
    for category in HIGH_VOLATILITY_CATEGORIES:
        events = [_event("2026-10-15", category)]
        assert is_high_vol_window_from_events(date(2026, 10, 15), events) is True, category


def test_is_high_vol_window_non_high_vol_false() -> None:
    events = [_event("2026-10-15", "GDP")]
    assert is_high_vol_window_from_events(date(2026, 10, 15), events) is False


def test_is_high_vol_window_explicit_flag_overrides_category() -> None:
    events = [{"event_date": "2026-10-15", "category": "GDP", "is_high_volatility": True}]
    assert is_high_vol_window_from_events(date(2026, 10, 15), events) is True


def test_is_high_vol_window_custom_window_days() -> None:
    events = [_event("2026-10-15", "CPI")]
    assert is_high_vol_window_from_events(date(2026, 10, 17), events, window_days=2) is True
    assert is_high_vol_window_from_events(date(2026, 10, 18), events, window_days=2) is False


def test_is_high_vol_window_from_events_empty() -> None:
    assert is_high_vol_window_from_events(date(2026, 10, 15), []) is False


def test_is_high_vol_window_missing_date_skipped() -> None:
    events = [{"category": "CPI"}, {}]
    assert is_high_vol_window_from_events(date(2026, 10, 15), events) is False


def test_default_window_days() -> None:
    assert DEFAULT_HIGH_VOL_WINDOW_DAYS == 1


# ── DB-backed tests (mocked session) ─────────────────────────────────────

def _calendar_row(event_date, category="CPI", is_high_volatility=True):
    row = MagicMock()
    row.event_date = event_date
    row.category = category
    row.is_high_volatility = is_high_volatility
    return row


def _make_session_with_rows(rows):
    """Mock session honouring the ``event_date BETWEEN`` filter of the query.

    The query binds two ``date`` params, so the mock filters the fixture rows
    against that window instead of returning everything.
    """
    session = MagicMock()

    def execute_side_effect(statement, *args, **kwargs):
        result = MagicMock()
        scalars = MagicMock()
        params = statement.compile().params
        bounds = sorted(v for v in params.values() if isinstance(v, date))
        if bounds:
            start, end = bounds[0], bounds[-1]
            filtered = [r for r in rows if start <= r.event_date <= end]
        else:
            filtered = list(rows)
        scalars.all.return_value = filtered
        result.scalars.return_value = scalars
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    return session


@pytest.mark.asyncio
async def test_is_high_vol_window_db_true() -> None:
    session = _make_session_with_rows([_calendar_row(date(2026, 10, 15), "CPI")])
    assert await is_high_vol_window(date(2026, 10, 15), session) is True


@pytest.mark.asyncio
async def test_is_high_vol_window_db_false_outside_window() -> None:
    session = _make_session_with_rows([_calendar_row(date(2026, 10, 20), "CPI")])
    assert await is_high_vol_window(date(2026, 10, 15), session) is False


@pytest.mark.asyncio
async def test_is_high_vol_window_db_category_based() -> None:
    session = _make_session_with_rows(
        [_calendar_row(date(2026, 10, 15), "FOMC", is_high_volatility=False)]
    )
    assert await is_high_vol_window(date(2026, 10, 15), session) is True


@pytest.mark.asyncio
async def test_is_high_vol_window_db_includes_iran_manual() -> None:
    session = _make_session_with_rows([_calendar_row(date(2026, 10, 15), "FX", True)])
    assert await is_high_vol_window(date(2026, 10, 15), session, include_iran_manual=True) is True


# ── Manual entry + listing ────────────────────────────────────────────────


def _make_insert_session(existing=None):
    """Mock session that returns ``existing`` for a by-id lookup and records adds."""
    session = MagicMock()
    added: list[object] = []

    def execute_side_effect(statement, *args, **kwargs):
        result = MagicMock()
        scalars = MagicMock()
        scalars.first.return_value = existing
        scalars.all.return_value = []
        result.scalars.return_value = scalars
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    session.commit = AsyncMock()
    session.add = MagicMock(side_effect=added.append)
    session.added = added
    return session


@pytest.mark.asyncio
async def test_add_iran_manual_event_inserts() -> None:
    session = _make_insert_session(existing=None)

    row = await add_iran_manual_event(
        session,
        event_id="iran-fx-2026-10-20",
        event_date=date(2026, 10, 20),
        title="Iran FX decision",
        category="FX",
        importance=2,
        note="manual",
        is_high_volatility=True,
    )

    assert len(session.added) == 1
    added_row = session.added[0]
    assert added_row.event_id == "iran-fx-2026-10-20"
    assert added_row.event_date == date(2026, 10, 20)
    assert added_row.is_high_volatility is True
    session.commit.assert_awaited_once()
    assert row is added_row


@pytest.mark.asyncio
async def test_add_iran_manual_event_is_idempotent() -> None:
    existing = _calendar_row(date(2026, 10, 20), "FX")
    existing.event_id = "iran-fx-2026-10-20"
    session = _make_insert_session(existing=existing)

    row = await add_iran_manual_event(
        session,
        event_id="iran-fx-2026-10-20",
        event_date=date(2026, 10, 20),
    )

    assert row is existing
    assert session.added == []
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_economic_calendar_returns_rows() -> None:
    rows = [_calendar_row(date(2026, 10, 15), "CPI")]

    async def execute_side_effect(statement, *args, **kwargs):
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = rows
        result.scalars.return_value = scalars
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute_side_effect)

    listed = await list_economic_calendar(session)

    assert listed == rows


@pytest.mark.asyncio
async def test_list_iran_manual_events_returns_rows() -> None:
    rows = [_calendar_row(date(2026, 10, 20), "FX")]

    async def execute_side_effect(statement, *args, **kwargs):
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = rows
        result.scalars.return_value = scalars
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute_side_effect)

    listed = await list_iran_manual_events(session)

    assert listed == rows
