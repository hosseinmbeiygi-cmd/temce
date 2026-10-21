"""Unit tests for ``get_gold_macro_live`` — stored-data macro posture.

No network or real database — the session is mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.gold_macro import (
    GoldEconomicCalendarEventModel,
    GoldIranManualEventModel,
    GoldMacroIndicatorModel,
)
from services.gold.macro_live import (
    DEFAULT_STALENESS_SECONDS,
    FRED_DXY_BROAD_INDICATOR,
    FRED_TIPS_10Y_INDICATOR,
    MacroLiveResult,
    get_gold_macro_live,
)


def _premium_row(indicator: str, value: float):
    row = MagicMock()
    row.indicator = indicator
    row.value = value
    return row


def _calendar_row(category="CPI", is_high_volatility=True, event_date=None):
    row = MagicMock()
    row.category = category
    row.is_high_volatility = is_high_volatility
    row.event_date = event_date
    return row


def _indicator_row(value, fetched_at_delta_seconds=None):
    row = MagicMock()
    row.value = value
    row.fetched_at = (
        datetime.now(UTC) - timedelta(seconds=fetched_at_delta_seconds)
        if fetched_at_delta_seconds is not None
        else None
    )
    return row


def _snapshot_row(xau_usd, snapshot_at_delta_seconds=None):
    row = MagicMock()
    row.xau_usd = xau_usd
    row.snapshot_at = (
        datetime.now(UTC) - timedelta(seconds=snapshot_at_delta_seconds)
        if snapshot_at_delta_seconds is not None
        else None
    )
    return row


DXY_HISTORY = [95.0 + 0.5 * i for i in range(60)]  # 95..124.5, p20≈100.9, p80≈118.6


def _make_session(
    tips=None,
    dxy=None,
    snapshots=None,
    calendar=None,
    iran=None,
    premiums=None,
    dxy_history=None,
):
    """Mock session that dispatches on the queried entity.

    ``select(Model)`` exposes the model through ``column_descriptions``, so the
    mock can answer indicator queries, snapshot queries and calendar queries
    independently.
    """
    session = MagicMock()
    indicator_calls: list[str] = []
    history = DXY_HISTORY if dxy_history is None else dxy_history

    def execute_side_effect(statement, *args, **kwargs):
        result = MagicMock()
        scalars = MagicMock()
        entity = statement.column_descriptions[0]["entity"]

        if entity is GoldMacroIndicatorModel:
            indicator = statement.compile().params.get("indicator_1")
            if indicator is not None and "PREMIUM_VS_SPOT" in str(indicator):
                # Pattern query (tokenized-gold premium) — returns a list.
                scalars.all.return_value = list(premiums or [])
            else:
                indicator_calls.append(indicator)
                if indicator == FRED_TIPS_10Y_INDICATOR:
                    scalars.first.return_value = tips
                elif indicator == FRED_DXY_BROAD_INDICATOR:
                    scalars.first.return_value = dxy
                    scalars.all.return_value = list(history)
                else:
                    scalars.first.return_value = None
        elif entity is GoldEconomicCalendarEventModel:
            scalars.all.return_value = list(calendar or [])
        elif entity is GoldIranManualEventModel:
            scalars.all.return_value = list(iran or [])
        else:
            rows = list(snapshots or [])
            scalars.all.return_value = rows

        result.scalars.return_value = scalars
        return result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    session.indicator_calls = indicator_calls
    return session


@pytest.mark.asyncio
async def test_get_gold_macro_live_full_inputs_bullish() -> None:
    session = _make_session(
        tips=_indicator_row(0.85),   # TIPS 10Y → accommodative
        dxy=_indicator_row(92.0),    # DXY → weak
        snapshots=[
            _snapshot_row(2100.0),   # latest
            _snapshot_row(2000.0),   # previous → up trend
        ],
    )
    result = await get_gold_macro_live(session)

    assert result.available is True
    assert result.missing == []
    assert result.posture["posture"] == "BULLISH"
    assert result.inputs["tips_yield"] == 0.85
    assert result.inputs["dxy_index"] == 92.0
    assert result.inputs["gold_trend"] == "up"


@pytest.mark.asyncio
async def test_get_gold_macro_live_missing_tips() -> None:
    session = _make_session(
        tips=None,
        dxy=_indicator_row(92.0),
        snapshots=[_snapshot_row(2100.0), _snapshot_row(2000.0)],
    )
    result = await get_gold_macro_live(session)

    assert result.available is False
    assert "tips_yield" in result.missing
    assert result.posture is None


@pytest.mark.asyncio
async def test_get_gold_macro_live_all_tables_empty() -> None:
    """With every source table empty the result degrades — it never raises."""
    session = _make_session(tips=None, dxy=None, snapshots=[], calendar=[], iran=[])
    result = await get_gold_macro_live(session)

    assert result.available is False
    assert result.posture is None
    assert result.error is None
    assert result.missing == ["tips_yield", "dxy_index", "gold_trend"]
    assert result.inputs == {}
    assert result.tips_staleness_seconds is None
    assert result.dxy_staleness_seconds is None
    assert result.high_vol_window is False


@pytest.mark.asyncio
async def test_get_gold_macro_live_stale_tips() -> None:
    session = _make_session(
        tips=_indicator_row(0.85, fetched_at_delta_seconds=DEFAULT_STALENESS_SECONDS + 1),
        dxy=_indicator_row(92.0),
        snapshots=[_snapshot_row(2100.0), _snapshot_row(2000.0)],
    )
    result = await get_gold_macro_live(session)

    assert result.available is False
    assert "tips_yield_stale" in result.missing


@pytest.mark.asyncio
async def test_get_gold_macro_live_sideways_trend() -> None:
    session = _make_session(
        tips=_indicator_row(1.5),
        dxy=_indicator_row(100.0),
        snapshots=[_snapshot_row(2000.0), _snapshot_row(2010.0)],  # +0.5% → sideways
    )
    result = await get_gold_macro_live(session)

    assert result.available is True
    assert result.inputs["gold_trend"] == "sideways"


@pytest.mark.asyncio
async def test_get_gold_macro_live_insufficient_snapshots() -> None:
    session = _make_session(
        tips=_indicator_row(0.85),
        dxy=_indicator_row(92.0),
        snapshots=[_snapshot_row(2100.0)],  # only one → no trend
    )
    result = await get_gold_macro_live(session)

    assert result.available is False
    assert "gold_trend" in result.missing


@pytest.mark.asyncio
async def test_get_gold_macro_live_down_trend_bearish() -> None:
    session = _make_session(
        tips=_indicator_row(2.5),   # restrictive
        dxy=_indicator_row(110.0),  # strong
        snapshots=[
            _snapshot_row(2000.0),   # latest
            _snapshot_row(2500.0),   # previous → down trend
        ],
    )
    result = await get_gold_macro_live(session)

    assert result.available is True
    assert result.inputs["gold_trend"] == "down"
    assert result.posture["posture"] == "BEARISH"


@pytest.mark.asyncio
async def test_broad_dxy_uses_stored_history_percentiles() -> None:
    """DTWEXBGS is ranked against its own stored history, not 95/105."""
    session = _make_session(
        tips=_indicator_row(1.5),
        dxy=_indicator_row(125.0),
        snapshots=[
            _snapshot_row(2000.0),
            _snapshot_row(2010.0),
        ],
    )
    result = await get_gold_macro_live(session)

    assert result.available is True
    assert result.posture["dxy_signal"] == "STRONG"
    assert result.posture["dxy_threshold_mode"] == "percentile"
    assert result.posture["dxy_percentile_high"] == pytest.approx(118.6, abs=0.1)
    assert result.inputs["dxy_history_samples"] == len(DXY_HISTORY)


@pytest.mark.asyncio
async def test_broad_dxy_without_history_is_insufficient_history() -> None:
    """Below the configured minimum the posture is explicitly non-directional."""
    session = _make_session(
        tips=_indicator_row(1.5),
        dxy=_indicator_row(110.0),
        snapshots=[
            _snapshot_row(2000.0),
            _snapshot_row(2010.0),
        ],
        dxy_history=[100.0] * 10,
    )
    result = await get_gold_macro_live(session)

    assert result.available is False
    assert "dxy_history" in result.missing
    assert result.posture is not None
    assert result.posture["posture"] == "insufficient_history"
    assert result.posture["dxy_signal"] == "INSUFFICIENT_HISTORY"
    assert result.posture["composite_score"] is None


def test_macro_live_result_defaults() -> None:
    result = MacroLiveResult(available=False, missing=["tips_yield"])
    assert result.available is False
    assert result.missing == ["tips_yield"]
    assert result.posture is None
    assert result.inputs == {}
    assert result.high_vol_window is False


@pytest.mark.asyncio
async def test_get_gold_macro_live_high_vol_window_from_calendar() -> None:
    """A CPI/NFP/FOMC event in the window flags the posture as high-vol."""
    session = _make_session(
        tips=_indicator_row(0.85),
        dxy=_indicator_row(92.0),
        snapshots=[_snapshot_row(2100.0), _snapshot_row(2000.0)],
        calendar=[_calendar_row(category="CPI")],
    )
    result = await get_gold_macro_live(session)

    assert result.high_vol_window is True
    # The window flag is context, not a missing input — posture still computes.
    assert result.available is True
    assert result.missing == []


@pytest.mark.asyncio
async def test_get_gold_macro_live_high_vol_window_from_iran_manual_event() -> None:
    session = _make_session(
        tips=_indicator_row(0.85),
        dxy=_indicator_row(92.0),
        snapshots=[_snapshot_row(2100.0), _snapshot_row(2000.0)],
        iran=[_calendar_row(category="FX", is_high_volatility=True)],
    )
    result = await get_gold_macro_live(session)

    assert result.high_vol_window is True


@pytest.mark.asyncio
async def test_get_gold_macro_live_no_high_vol_window() -> None:
    session = _make_session(
        tips=_indicator_row(0.85),
        dxy=_indicator_row(92.0),
        snapshots=[_snapshot_row(2100.0), _snapshot_row(2000.0)],
    )
    result = await get_gold_macro_live(session)

    assert result.high_vol_window is False


@pytest.mark.asyncio
async def test_get_gold_macro_live_high_vol_window_ignores_low_vol_category() -> None:
    """A non-CPI/NFP/FOMC event without the high-vol flag is not a window."""
    session = _make_session(
        tips=_indicator_row(0.85),
        dxy=_indicator_row(92.0),
        snapshots=[_snapshot_row(2100.0), _snapshot_row(2000.0)],
        calendar=[_calendar_row