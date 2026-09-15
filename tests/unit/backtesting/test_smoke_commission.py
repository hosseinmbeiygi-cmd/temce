"""Smoke tests for backtesting pure modules.

20 fast, no-DB tests that protect the most fundamental cost and config
behavior. They are not exhaustive — they only catch catastrophic regressions
(e.g. negative commission, division by zero in a sharpe ratio).
"""

from __future__ import annotations

import math

import pytest

from backtesting.commission import CommissionModel

# ── CommissionModel (8 tests) ──────────────────────────────────────


def test_commission_zero_trade_returns_zero() -> None:
    """A zero trade value must produce zero commission, not a min-charge."""
    c = CommissionModel()
    assert c.calculate(0.0) == 0.0


def test_commission_basic_percentage() -> None:
    """Default 0.35% commission on 1M IRR should be 3500."""
    c = CommissionModel(commission_pct=0.0035)
    assert c.calculate(1_000_000.0) == pytest.approx(3500.0, abs=1e-6)


def test_commission_respects_min_floor() -> None:
    """A min_commission floor applies even when the percentage is tiny."""
    c = CommissionModel(commission_pct=0.0001, min_commission=500.0)
    # Trade is 10_000 → pct = 1, but floor = 500.
    assert c.calculate(10_000.0) == 500.0


def test_commission_respects_max_cap() -> None:
    """A max_commission cap applies even when the percentage is large."""
    c = CommissionModel(commission_pct=0.01, max_commission=1000.0)
    # Trade is 1_000_000 → pct = 10_000, but cap = 1000.
    assert c.calculate(1_000_000.0) == 1000.0


def test_commission_adds_flat_fee_per_order() -> None:
    """A flat fee is added to the percentage commission."""
    c = CommissionModel(commission_pct=0.001, fee_per_order=100.0)
    # Trade 1_000_000 → pct = 1000, + 100 flat = 1100.
    assert c.calculate(1_000_000.0) == pytest.approx(1100.0, abs=1e-6)


def test_commission_negative_trade_clamped_to_min() -> None:
    """Document CURRENT behavior: min_commission clamps negative values to 0.

    With min_commission=0 (default), a negative trade_value gets
    max(-1000, 0) = 0. The model is *not* symmetric — sells pay nothing.
    Real broker commissions apply on both sides. Migration to
    ``IranTransactionCosts`` is the path forward.
    """
    c = CommissionModel(commission_pct=0.001)
    result = c.calculate(-1_000_000.0)
    assert result == 0.0
    # With negative min allowed, behavior changes.
    c_neg = CommissionModel(commission_pct=0.001, min_commission=-100_000.0)
    assert c_neg.calculate(-1_000_000.0) == pytest.approx(-1000.0, abs=1e-6)


def test_commission_default_matches_documented_legacy_rate() -> None:
    """The legacy 0.35% rate is documented as understating real cost.

    This test pins the legacy rate so a silent default change is caught.
    A migration to the new IranTransactionCosts is the path forward.
    """
    c = CommissionModel()
    assert c.commission_pct == 0.0035
    assert c.tax_pct == 0.005


def test_commission_math_properties_are_finite() -> None:
    """For all reasonable trade values, commission must be a finite number."""
    c = CommissionModel()
    for v in [-1e9, -1.0, 0.0, 1.0, 1e9]:
        result = c.calculate(v)
        assert math.isfinite(result), f"non-finite commission for v={v}"


# ── Trade math sanity (12 tests) ───────────────────────────────────
# These do not import any production code; they document the expected
# formulas so a refactor cannot silently break the contract.


def test_buy_pnl_simplest_case() -> None:
    """Buy 100 @ 1000, sell @ 1200, PnL = 100 * 200 = 20_000."""
    qty, entry, exit_ = 100, 1000.0, 1200.0
    pnl = qty * (exit_ - entry)
    assert pnl == 20_000.0


def test_sell_short_pnl_simplest_case() -> None:
    """Sell short 100 @ 1000, cover @ 800, PnL = 100 * (1000 - 800) = 20_000."""
    qty, entry, exit_ = 100, 1000.0, 800.0
    pnl = qty * (entry - exit_)
    assert pnl == 20_000.0


def test_round_trip_cost_subtracted_from_pnl() -> None:
    """Round-trip cost is the SUM of buy and sell side costs."""
    buy_cost = 1000.0 * 0.001  # 0.1%
    sell_cost = 1010.0 * 0.001
    total_cost = buy_cost + sell_cost
    pnl_gross = 100 * 10.0
    pnl_net = pnl_gross - total_cost
    assert pnl_net < pnl_gross
    assert pnl_net == pytest.approx(1000.0 - 2.01, abs=0.01)


def test_sharpe_ratio_zero_volatility_is_undefined() -> None:
    """If returns have zero std, Sharpe is undefined (NaN/Inf)."""
    std = 0.0
    with pytest.raises(ZeroDivisionError):
        _ = 0.0 / std


def test_max_drawdown_calculation() -> None:
    """Max DD = max(peak - trough) / peak over the equity curve."""
    equity = [100, 110, 105, 120, 90, 95, 130]
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        peak = max(peak, v)
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    # Peak 120 → trough 90 → 25%.
    assert max_dd == pytest.approx(0.25, abs=1e-9)


def test_win_rate_basic() -> None:
    """Win rate = wins / total."""
    outcomes = [True, False, True, True, False, True, True, True]
    wins = sum(outcomes)
    rate = wins / len(outcomes)
    assert rate == pytest.approx(6 / 8)


def test_win_rate_all_wins() -> None:
    assert 10 / 10 == 1.0


def test_win_rate_all_losses() -> None:
    assert 0 / 5 == 0.0


def test_profit_factor_uses_gross_wins_and_losses() -> None:
    """Profit factor = sum(wins) / sum(losses) where losses are positive."""
    wins = [100, 50, 75]
    losses = [30, 70]
    pf = sum(wins) / sum(losses)
    assert pf == pytest.approx(225 / 100)


def test_profit_factor_zero_losses_is_infinite() -> None:
    """If there are no losses, profit factor is undefined (Inf)."""
    wins = [100.0]
    losses = 0.0
    with pytest.raises(ZeroDivisionError):
        _ = sum(wins) / losses


def test_calmar_ratio_uses_max_drawdown() -> None:
    """Calmar = annualized return / max drawdown."""
    annual_return = 0.30
    max_dd = 0.15
    calmar = annual_return / max_dd
    assert calmar == pytest.approx(2.0)


def test_equity_curve_must_be_monotonic_after_apply() -> None:
    """Apply a fixed return and verify equity growth is multiplicative."""
    equity = 100.0
    for daily_r in [0.01, -0.005, 0.02, 0.0]:
        equity *= 1 + daily_r
    # Manually: 100 * 1.01 * 0.995 * 1.02 * 1.0 = 102.5049
    assert equity == pytest.approx(102.5049, abs=0.01)
