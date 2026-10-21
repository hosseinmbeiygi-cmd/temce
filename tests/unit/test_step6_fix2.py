"""STEP 6-FIX-2 gate tests: econ-calendar seed, FRED blocked-by-data, mint-fee unity.

Gate: min/max seed date, event categories, is_high_vol_window true/false at
boundaries; no fake FRED rows without FRED_API_KEY; IR_COIN_EMAMI fee unified.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from providers.macro_sources.economic_calendar import (  # noqa: E402
    DEFAULT_SEED_EVENTS,
    SeededEconomicCalendarProvider,
)
from services.gold.economic_calendar import (  # noqa: E402
    is_high_vol_window_from_events,
)


def _dates() -> list[date]:
    return sorted(date.fromisoformat(e["event_date"]) for e in DEFAULT_SEED_EVENTS)


def test_seed_covers_required_range():
    dates = _dates()
    assert dates[0] >= date(2026, 10, 19), f"min seed date {dates[0]} before today"
    assert dates[-1] >= date(2027, 6, 30), f"max seed date {dates[-1]} < 2027-06-30"
    assert dates[0] == date(2026, 10, 28)  # first in-range event: FOMC statement
    assert dates[-1] == date(2027, 7, 14)  # last: Jun-2027 CPI (past 2027-06-30)


def test_seed_categories_and_count():
    cats = {e["category"] for e in DEFAULT_SEED_EVENTS}
    assert cats == {"CPI", "NFP", "FOMC"}
    assert len(DEFAULT_SEED_EVENTS) == 9 + 9 + 6  # CPI + NFP + FOMC
    assert all(e["is_high_volatility"] for e in DEFAULT_SEED_EVENTS)


def test_default_provider_serves_seed():
    assert len(SeededEconomicCalendarProvider().fetch()) == len(DEFAULT_SEED_EVENTS)


def test_high_vol_window_boundaries():
    events = list(DEFAULT_SEED_EVENTS)
    # On the event day and ±1 day → True (default window_days=1).
    assert is_high_vol_window_from_events(date(2026, 10, 28), events) is True
    assert is_high_vol_window_from_events(date(2026, 10, 27), events) is True
    assert is_high_vol_window_from_events(date(2026, 10, 29), events) is True
    # ±2 days → False.
    assert is_high_vol_window_from_events(date(2026, 10, 26), events) is False
    assert is_high_vol_window_from_events(date(2026, 10, 30), events) is False
    # A far date with no nearby event → False.
    assert is_high_vol_window_from_events(date(2026, 10, 20), events) is False


def test_fred_blocked_without_key_no_fake_rows():
    if os.environ.get("FRED_API_KEY"):
        pytest.skip("FRED_API_KEY is set — live sync path, not the blocked path")
    from providers.macro_sources.base import MacroSourceError
    from providers.macro_sources.fred import FREDClient

    with pytest.raises(MacroSourceError, match="FRED_API_KEY"):
        FREDClient().fetch()


def test_emami_mint_fee_unified():
    import services.gold.constants as svc
    import src.gold_desk.constants as desk

    assert svc.COIN_MINTING_COSTS["IR_COIN_EMAMI"] == 80_000.0
    assert desk.COIN_MINTING_COSTS["IR_COIN_EMAMI"] == 80_000.0
    assert svc.COIN_SPECS["emami"]["mint_fee_irr"] == 80_000.0
