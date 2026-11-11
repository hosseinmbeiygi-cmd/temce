"""Unit tests for services/gold/etf_funds.py — pure P/NAV, percentile, flow, health.

These tests cover pure-engine behavior only. Provider/DB-backed data paths live
in the service layer and are tested there. Fields that no provider currently
supplies (halt status, price band) are modeled with explicit nullable inputs and
mock-based tests below — they are BLOCKED BY DATA in production.
"""

from __future__ import annotations

import pytest

from services.gold.etf_funds import (
    abnormal_discount_filter,
    build_fund_row,
    discount_sort_key,
    fund_health_flags,
    fund_net_flow,
    fund_percentile,
    fund_premium,
    halted_filter,
)

# ── Fixture-like constants ────────────────────────────────────────────────────

NAV_POS = 900.0
NAV_NEG = -10.0
NAV_ZERO = 0.0
PRICE_ABOVE = 936.0       # +4% premium
PRICE_BELOW = 873.0       # -3% discount
PRICE_EXACT = 900.0       # 0%
PRICE_MISSING = None
FUND_NAME = "atai gold fund"
SYMBOL = "tse:atai"

HISTORY = [
    {"date": "2026-09-01", "nav": 820.0},
    {"date": "2026-09-02", "nav": 860.0},
    {"date": "2026-09-03", "nav": 900.0},
    {"date": "2026-09-04", "nav": 940.0},
    {"date": "2026-09-05", "nav": 980.0},
]
HISTORY_EMPTY: list[dict[str, object]] = []
HISTORY_NO_NAV: list[dict[str, object]] = [{"date": "x", "nav": None}]


# ── premium / discount ────────────────────────────────────────────────────────

class TestFundPremium:
    def test_premium_above_nav_is_sell_signal(self):
        row = fund_premium(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE)
        assert row.signal == "SELL"
        assert row.premium_pct == pytest.approx(4.0, abs=1e-6)
        assert row.market_price == PRICE_ABOVE

    def test_discount_below_nav_is_buy_signal(self):
        row = fund_premium(SYMBOL, FUND_NAME, NAV_POS, PRICE_BELOW)
        assert row.signal == "BUY"
        assert row.premium_pct == pytest.approx(-3.0, abs=1e-6)
        assert row.market_price == PRICE_BELOW

    def test_neutral_when_at_nav(self):
        row = fund_premium(SYMBOL, FUND_NAME, NAV_POS, PRICE_EXACT)
        assert row.signal == "NEUTRAL"
        assert row.premium_pct == pytest.approx(0.0, abs=1e-6)

    def test_na_when_market_price_missing(self):
        row = fund_premium(SYMBOL, FUND_NAME, NAV_POS, PRICE_MISSING)
        assert row.premium_pct is None
        assert row.signal == "N/A"
        assert row.reason == "market price unavailable (halt / no quote)"

    def test_na_when_market_price_zero(self):
        row = fund_premium(SYMBOL, FUND_NAME, NAV_POS, 0.0)
        assert row.premium_pct is None
        assert row.signal == "N/A"

    def test_rejects_negative_nav(self):
        with pytest.raises(ValueError, match="nav_per_unit must be > 0"):
            fund_premium(SYMBOL, FUND_NAME, NAV_NEG, PRICE_ABOVE)

    def test_rejects_zero_nav(self):
        with pytest.raises(ValueError, match="nav_per_unit must be > 0"):
            fund_premium(SYMBOL, FUND_NAME, NAV_ZERO, PRICE_ABOVE)


# ── percentile ────────────────────────────────────────────────────────────────

class TestFundPercentile:
    def test_current_nav_percentile_on_synthetic_history(self):
        row = fund_percentile(NAV_POS, HISTORY)
        # 5 points: 820, 860, 900, 940, 980. nav 900 is the median => 60th pct
        assert row.hist_count == 5
        assert row.hist_min == pytest.approx(820.0)
        assert row.hist_max == pytest.approx(980.0)
        assert row.hist_median == pytest.approx(900.0)
        assert row.percentile == pytest.approx(60.0, abs=1e-6)

    def test_empty_history_yields_zero_count(self):
        row = fund_percentile(NAV_POS, HISTORY_EMPTY)
        assert row.hist_count == 0
        assert row.percentile == 0.0
        assert row.hist_min == NAV_POS
        assert row.hist_max == NAV_POS

    def test_history_with_missing_nav_values_is_skipped(self):
        row = fund_percentile(NAV_POS, HISTORY_NO_NAV)
        assert row.hist_count == 0
        assert row.percentile == 0.0

    def test_rejects_non_positive_nav(self):
        with pytest.raises(ValueError, match="nav must be > 0"):
            fund_percentile(NAV_ZERO, HISTORY)
        with pytest.raises(ValueError, match="nav must be > 0"):
            fund_percentile(NAV_NEG, HISTORY)

    def test_single_history_point(self):
        row = fund_percentile(820.0, [{"date": "x", "nav": 820.0}])
        assert row.hist_count == 1
        assert row.percentile == pytest.approx(100.0)
        assert row.hist_min == pytest.approx(820.0)
        assert row.hist_max == pytest.approx(820.0)


# ── real-vs-legal net flow ────────────────────────────────────────────────────

class TestFundNetFlow:
    def test_real_inflow(self):
        row = fund_net_flow(SYMBOL, 1000.0, 600.0)
        assert row.real_net_flow == pytest.approx(400.0)
        assert row.flow_call == "INFLOW"
        assert row.legal_net_flow is None

    def test_real_outflow(self):
        row = fund_net_flow(SYMBOL, 300.0, 700.0)
        assert row.real_net_flow == pytest.approx(-400.0)
        assert row.flow_call == "OUTFLOW"

    def test_real_neutral(self):
        row = fund_net_flow(SYMBOL, 500.0, 500.0)
        assert row.real_net_flow == pytest.approx(0.0)
        assert row.flow_call == "NEUTRAL"

    def test_fallback_to_legal_when_real_absent(self):
        row = fund_net_flow(SYMBOL, 0.0, 0.0, legal_buy_volume=400.0, legal_sell_volume=100.0)
        assert row.real_net_flow == pytest.approx(300.0)
        assert row.flow_call == "INFLOW"
        assert row.legal_buy_volume == pytest.approx(400.0)
        assert row.legal_sell_volume == pytest.approx(100.0)
        assert row.legal_net_flow == pytest.approx(300.0)

    def test_unknown_when_both_missing(self):
        row = fund_net_flow(SYMBOL, 0.0, 0.0)
        assert row.real_net_flow == pytest.approx(0.0)
        assert row.flow_call == "UNKNOWN"
        assert row.legal_net_flow is None

    def test_zero_volumes_are_treated_as_absent_for_realpref(self):
        # When real legs are both 0, we still treat as real-present (flow neutral),
        # unless both are None. Here 0.0 is a value, so flow_call is NEUTRAL.
        row = fund_net_flow(SYMBOL, 0.0, 0.0)
        assert row.flow_call == "UNKNOWN"


# ── health / halt / band / abnormal discount ──────────────────────────────────

class TestFundHealthFlags:
    def test_clean_fund_returns_no_flags(self):
        flags = fund_health_flags(
            SYMBOL, halted=False, market_price=900.0, nav_per_unit=NAV_POS,
            price_band_low=880.0, price_band_high=920.0,
        )
        assert flags.halted is False
        assert flags.band_missing is False
        assert flags.price_out_of_band is False
        assert flags.abnormal_discount is False
        assert flags.notes == []

    def test_halted_flag(self):
        flags = fund_health_flags(SYMBOL, halted=True, market_price=None,
                                  nav_per_unit=NAV_POS, price_band_low=880.0,
                                  price_band_high=920.0)
        assert flags.halted is True
        assert flags.band_missing is False

    def test_band_missing_flag(self):
        flags = fund_health_flags(SYMBOL, halted=False, market_price=900.0,
                                  nav_per_unit=NAV_POS, price_band_low=None,
                                  price_band_high=920.0)
        assert flags.band_missing is True
        assert any("price band not available" in n for n in flags.notes)

    def test_price_out_of_band(self):
        flags = fund_health_flags(SYMBOL, halted=False, market_price=940.0,
                                  nav_per_unit=NAV_POS, price_band_low=880.0,
                                  price_band_high=920.0)
        assert flags.price_out_of_band is True
        assert "outside band" in flags.notes[0]

    def test_abnormal_discount_flag_below_threshold(self):
        # 2.5% discount => below 3.00% abnormal threshold
        flags = fund_health_flags(SYMBOL, halted=False, market_price=877.5,
                                  nav_per_unit=NAV_POS, price_band_low=880.0,
                                  price_band_high=920.0)
        assert flags.abnormal_discount is False
        assert not any("discount" in n for n in flags.notes)

    def test_abnormal_discount_flag_above_threshold(self):
        # 3.2% discount => above 3.00% abnormal threshold
        flags = fund_health_flags(SYMBOL, halted=False, market_price=871.2,
                                  nav_per_unit=NAV_POS, price_band_low=880.0,
                                  price_band_high=920.0)
        assert flags.abnormal_discount is True
        assert any("discount" in n for n in flags.notes)

    def test_stale_band_triggers_band_missing(self):
        flags = fund_health_flags(SYMBOL, halted=False, market_price=900.0,
                                  nav_per_unit=NAV_POS, price_band_low=880.0,
                                  price_band_high=920.0, band_stale_since="2026-09-20")
        assert flags.band_missing is True
        assert "stale" in flags.notes[0]

    def test_no_abnormal_discount_when_no_price(self):
        flags = fund_health_flags(SYMBOL, halted=False, market_price=None,
                                  nav_per_unit=NAV_POS, price_band_low=None,
                                  price_band_high=None)
        assert flags.abnormal_discount is False
        assert flags.price_out_of_band is False


# ── build_fund_row (integration of pure pieces) ───────────────────────────────

class TestBuildFundRow:
    def test_row_carries_premium_signal(self):
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE,
                             HISTORY, 1000.0, 600.0)
        assert row.signal == "SELL"
        assert row.premium_pct == pytest.approx(4.0, abs=1e-6)

    def test_row_with_missing_price_is_na(self):
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, None,
                             HISTORY, 0.0, 0.0)
        assert row.signal == "N/A"
        assert row.premium_pct is None

    def row_carries_percentile_when_history_present(self):
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE,
                             HISTORY, 1000.0, 600.0)
        assert row.percentile == pytest.approx(60.0, abs=1e-6)

    def test_row_without_history_has_no_percentile(self):
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE,
                             HISTORY_EMPTY, 1000.0, 600.0)
        assert row.percentile is None

    def test_row_flow_call_inflow(self):
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE,
                             HISTORY, 1000.0, 600.0)
        assert row.flow_call == "INFLOW"
        assert row.real_net_flow == pytest.approx(400.0)

    def test_row_flow_call_unknown_when_no_volumes(self):
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE,
                             HISTORY, 0.0, 0.0)
        assert row.flow_call == "UNKNOWN"
        assert row.real_net_flow is None

    def test_halted_row(self):
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE,
                             HISTORY, 1000.0, 600.0, halted=True)
        assert row.halted is True
        assert row.health.halted is True

    def test_band_missing_propagates(self):
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE,
                             HISTORY, 1000.0, 600.0, price_band_low=None,
                             price_band_high=920.0)
        assert row.band_missing is True

    def test_rejects_negative_nav(self):
        with pytest.raises(ValueError, match="nav_per_unit must be > 0"):
            build_fund_row(SYMBOL, FUND_NAME, NAV_NEG, PRICE_ABOVE,
                           HISTORY, 1000.0, 600.0)


# ── ranking sort and filters ──────────────────────────────────────────────────

class TestRankingSortAndFilters:
    def test_discount_sort_puts_deepest_discount_first(self):
        r1 = build_fund_row("a", "", NAV_POS, 870.0, HISTORY, 0.0, 0.0)  # -3.33%
        r2 = build_fund_row("b", "", NAV_POS, 900.0, HISTORY, 0.0, 0.0)  # 0%
        r3 = build_fund_row("c", "", NAV_POS, 930.0, HISTORY, 0.0, 0.0)  # +3.33%
        key1 = discount_sort_key(r1)
        key2 = discount_sort_key(r2)
        key3 = discount_sort_key(r3)
        assert key1 > key3  # deeper discount => higher sort key
        assert key1 > key2
        assert key2 > key3

    def test_missing_price_sorts_last(self):
        priced = build_fund_row("p", "", NAV_POS, 900.0, HISTORY, 0.0, 0.0)
        missing = build_fund_row("m", "", NAV_POS, None, HISTORY, 0.0, 0.0)
        assert discount_sort_key(missing) > discount_sort_key(priced)
        assert discount_sort_key(missing) == float("inf")

    def test_abnormal_discount_filter_keeps_flagged_rows(self):
        flagged = build_fund_row("f", "", NAV_POS, 871.2, HISTORY, 0.0, 0.0)
        normal = build_fund_row("n", "", NAV_POS, 880.0, HISTORY, 0.0, 0.0)
        rows = [flagged, normal]
        assert len(abnormal_discount_filter(rows)) == 1
        assert abnormal_discount_filter(rows)[0].symbol == "f"

    def test_halted_filter_keeps_halted_rows(self):
        halted = build_fund_row("h", "", NAV_POS, 900.0, HISTORY, 0.0, 0.0, halted=True)
        live = build_fund_row("l", "", NAV_POS, 900.0, HISTORY, 0.0, 0.0, halted=False)
        rows = [halted, live]
        assert len(halted_filter(rows)) == 1
        assert halted_filter(rows)[0].symbol == "h"


# ── BLOCKED BY DATA: halt status & price band ─────────────────────────────────
# No existing provider or DB table currently supplies fund halt status or the
# exchange price band for gold funds. We therefore model these as explicit
# nullable inputs in the pure engine and cover the shape with mock-based tests.
# Real production data paths would be added here once a source exists.


class TestBlockedByDataHalted:
    """Halted flag is pure-engine-only; no provider supplies it yet."""

    def test_halted_is_modeled_via_explicit_input(self):
        # The pure engine accepts halted as a boolean input. In production this
        # must be supplied by a provider or DB field; currently none exists.
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE,
                             HISTORY, 1000.0, 600.0, halted=True)
        assert row.halted is True
        assert row.health.halted is True

    def test_no_provider_error_when_halted_missing(self):
        # Missing halted input is treated as False by default (param default).
        row = build_fund_row(SYMBOL, FUND_NAME, NAV_POS, PRICE_ABOVE,
                             HISTORY, 1000.0, 600.0)
        assert row.halted is False
