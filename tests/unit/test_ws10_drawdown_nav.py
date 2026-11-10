"""WS10: oos_max_drawdown_pct sign convention + gold_fund_nav staleness coverage.

RED (before fixes):
  1. _max_drawdown_pct not unit-tested — sign convention UNVERIFIED (PHASE0 item 10).
  2. NAV staleness coverage (brsapi_nav_records) not confirmed in FRESHNESS_SOURCES.

GREEN (after fixes):
  1. _max_drawdown_pct returns a **positive** magnitude (percentage of decline from
     the running peak). Convention: 10.0 = 10% drawdown, NOT -10.0.
     This is consistent with max_drawdown_pct and oos_max_drawdown_pct in BacktestMetrics.
  2. FRESHNESS_SOURCES contains 'brsapi_nav_records' with calendar='jalali',
     confirming that NAV staleness IS monitored by trade-date (ISSUE-127: ingest
     date would make a 3-week-stale NAV look fresh — now fixed).
  3. FRESHNESS_SOURCES also contains 'gold_fund_nav' (job-run time, separate signal).

WS10 scope: pure-function + static config tests only.
Live verification (last row of brsapi_nav_records) requires a running database.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── 1. Import check ─────────────────────────────────────────────────────────

def test_import_drawdown_and_freshness():
    """_max_drawdown_pct and FRESHNESS_SOURCES must be importable.

    RED: not tested.
    GREEN: both importable.
    """
    from src.gold_desk.backtest_runner import _max_drawdown_pct  # noqa: F401
    from src.gold_desk.freshness import FRESHNESS_SOURCES  # noqa: F401


# ─── 2. _max_drawdown_pct edge cases ─────────────────────────────────────────

def test_max_drawdown_empty_nav_returns_zero():
    """Empty NAV array must return 0.0, not raise.

    RED: not tested.
    GREEN: guard `if nav.size == 0` returns 0.0.
    """
    from src.gold_desk.backtest_runner import _max_drawdown_pct

    result = _max_drawdown_pct(np.array([], dtype=float))
    assert result == 0.0


def test_max_drawdown_all_zero_returns_zero():
    """NAV that never rises above zero (peak never > 0) must return 0.0.

    RED: not tested.
    GREEN: `valid = peak > 0` check covers this case.
    """
    from src.gold_desk.backtest_runner import _max_drawdown_pct

    result = _max_drawdown_pct(np.array([0.0, 0.0, 0.0]))
    assert result == 0.0


def test_max_drawdown_monotonically_increasing_returns_zero():
    """NAV that only rises never has a drawdown.

    RED: not tested.
    GREEN: (peak - nav) / peak == 0 for every point.
    """
    from src.gold_desk.backtest_runner import _max_drawdown_pct

    result = _max_drawdown_pct(np.array([100.0, 110.0, 120.0, 130.0]))
    assert result == pytest.approx(0.0)


def test_max_drawdown_single_drop_positive_magnitude():
    """[100, 90] → 10.0 (10% drawdown expressed as positive magnitude).

    RED: sign convention UNVERIFIED — PHASE0 item 10.
    GREEN: (100-90)/100 * 100 = 10.0, returned as positive float.
    """
    from src.gold_desk.backtest_runner import _max_drawdown_pct

    result = _max_drawdown_pct(np.array([100.0, 90.0]))
    assert result == pytest.approx(10.0)
    assert result > 0, "max_drawdown_pct must be positive (magnitude, not signed loss)"


def test_max_drawdown_full_recovery_uses_trough_not_final():
    """[100, 90, 100] → 10.0 (the worst trough, even though NAV recovered).

    RED: not tested.
    GREEN: max(drawdown array) captures the worst intermediate point.
    """
    from src.gold_desk.backtest_runner import _max_drawdown_pct

    result = _max_drawdown_pct(np.array([100.0, 90.0, 100.0]))
    assert result == pytest.approx(10.0)


def test_max_drawdown_takes_worst_peak_not_first():
    """[100, 90, 110, 80]: peak rises to 110 then falls to 80 → 27.27%.

    RED: not tested.
    GREEN: running peak accumulate correctly picks 110 as the reference.
    """
    from src.gold_desk.backtest_runner import _max_drawdown_pct

    result = _max_drawdown_pct(np.array([100.0, 90.0, 110.0, 80.0]))
    # peak = [100, 100, 110, 110]; worst = (110-80)/110 * 100 ≈ 27.27
    expected = (110.0 - 80.0) / 110.0 * 100.0
    assert result == pytest.approx(expected, rel=1e-4)


def test_max_drawdown_always_non_negative():
    """max_drawdown_pct must be >= 0 for any NAV series.

    RED: not tested.
    GREEN: formula (peak - nav) / peak * 100 ≥ 0 because nav ≤ peak always.
    """
    from src.gold_desk.backtest_runner import _max_drawdown_pct

    for nav in [
        np.array([100.0, 95.0, 85.0, 75.0]),   # steady decline
        np.array([80.0, 100.0, 60.0, 90.0]),    # up then deep drop then partial recovery
        np.array([50.0, 50.0, 50.0]),            # flat
    ]:
        assert _max_drawdown_pct(nav) >= 0.0, f"negative drawdown for nav={nav}"


# ─── 3. NAV staleness coverage ───────────────────────────────────────────────

def test_freshness_sources_has_brsapi_nav_records_jalali():
    """brsapi_nav_records must be in FRESHNESS_SOURCES with calendar='jalali'.

    RED: coverage UNVERIFIED — PHASE0 item 10.
    GREEN: source added with calendar='jalali' so staleness is measured by
           trade-date (ISSUE-127: gregorian_date = ingest date, not trade date).
    """
    from src.gold_desk.freshness import FRESHNESS_SOURCES

    keys = {s.key for s in FRESHNESS_SOURCES}
    assert "brsapi_nav_records" in keys, (
        "brsapi_nav_records not found in FRESHNESS_SOURCES — "
        "NAV staleness is unmonitored"
    )
    nav_source = next(s for s in FRESHNESS_SOURCES if s.key == "brsapi_nav_records")
    assert nav_source.calendar == "jalali", (
        "brsapi_nav_records must use calendar='jalali' to measure NAV trade-date "
        "freshness, not gregorian_date (ingest time)"
    )


def test_freshness_sources_has_gold_fund_nav():
    """gold_fund_nav (job-run snapshot_at) must also be in FRESHNESS_SOURCES.

    RED: not confirmed.
    GREEN: source present; monitors when the nightly NAV job last ran.
    """
    from src.gold_desk.freshness import FRESHNESS_SOURCES

    keys = {s.key for s in FRESHNESS_SOURCES}
    assert "gold_fund_nav" in keys, (
        "gold_fund_nav not found in FRESHNESS_SOURCES"
    )
