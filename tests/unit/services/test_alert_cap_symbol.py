"""Regression tests for audit findings F6 + F7 — per-user alert cap and best-effort
symbol existence check (ممیزی 2026-11-28).

F6: per-IP rate limiting already existed (120/min); the missing piece was a cap on the
*stored* alert count per user. ``AlertService.count_alerts`` + the endpoint helper
``alert_cap_reached`` implement it; an unreadable count (-1) never blocks creation.

F7: ``AlertService.symbol_known`` checks the synced TSETMC tables; the create response
carries ``symbol_resolvable`` so the UI can warn that a hand-typed symbol may never
evaluate. None (unreadable tables) must not block creation either.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.alert_service import AlertService


# ── F6: count_alerts ────────────────────────────────────────────────────────────


def _session_with_scalar(value) -> MagicMock:
    session = MagicMock()
    session.scalar = AsyncMock(return_value=value)
    return session


@pytest.mark.asyncio
async def test_count_alerts_returns_total():
    svc = AlertService(_session_with_scalar(7))
    assert await svc.count_alerts("usr_demo") == 7


@pytest.mark.asyncio
async def test_count_alerts_zero_when_no_rows():
    svc = AlertService(_session_with_scalar(0))
    assert await svc.count_alerts("usr_demo") == 0


@pytest.mark.asyncio
async def test_count_alerts_unreadable_returns_minus_one():
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=RuntimeError("db down"))
    svc = AlertService(session)
    assert await svc.count_alerts("usr_demo") == -1


def test_alert_cap_reached_boundaries():
    from apps.api.endpoints.alerts import alert_cap_reached

    assert alert_cap_reached(199) is False
    assert alert_cap_reached(200) is True
    assert alert_cap_reached(500) is True
    assert alert_cap_reached(-1) is False  # unreadable count must not block creation


# ── F7: symbol_known ────────────────────────────────────────────────────────────


def _session_with_rows(first_row, second_row=object()) -> MagicMock:
    """Session whose execute() returns .first() results in call order."""
    results = []
    for row in (first_row, second_row):
        result = MagicMock()
        result.first.return_value = row
        results.append(result)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=results)
    return session


@pytest.mark.asyncio
async def test_symbol_known_in_details():
    svc = AlertService(_session_with_rows(MagicMock()))  # details hit → True
    assert await svc.symbol_known("فولاد") is True


@pytest.mark.asyncio
async def test_symbol_known_in_snapshots():
    svc = AlertService(_session_with_rows(None, MagicMock()))  # details miss, snapshot hit
    assert await svc.symbol_known("فولاد") is True


@pytest.mark.asyncio
async def test_symbol_unknown_returns_false():
    svc = AlertService(_session_with_rows(None, None))
    assert await svc.symbol_known("NOT_A_REAL_SYMBOL_XYZ") is False


@pytest.mark.asyncio
async def test_symbol_known_blank_symbol_is_false():
    svc = AlertService(MagicMock())
    assert await svc.symbol_known("   ") is False


@pytest.mark.asyncio
async def test_symbol_known_unreadable_tables_return_none():
    session = MagicMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))
    svc = AlertService(session)
    assert await svc.symbol_known("فولاد") is None
