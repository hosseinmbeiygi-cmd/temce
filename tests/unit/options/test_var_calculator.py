"""Tests for VaR / CVaR calculator.

These functions drive real capital-allocation decisions. A silent regression
in `historical_simulation` (e.g. empty tail) would under-report risk.
"""

from __future__ import annotations

import numpy as np
import pytest

from domain.options.var_calculator import VaRCalculator


def _returns(n: int = 250, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 0.02, size=n)


def test_historical_simulation_basic() -> None:
    r = _returns()
    result = VaRCalculator.historical_simulation(r, portfolio_value=1_000_000)
    assert result.method == "historical"
    assert result.portfolio_value == 1_000_000
    # VaR is a loss measure; absolute values are positive.
    assert result.var_95 > 0
    assert result.var_99 > result.var_95  # 99% tail is worse
    # CVaR >= VaR at same confidence.
    assert result.cvar_95 >= result.var_95
    assert result.cvar_99 >= result.var_99
    # pcts match absolute values.
    assert result.var_95 == pytest.approx(result.var_95_pct * 1_000_000, rel=1e-9)


def test_historical_simulation_too_few_returns_raises() -> None:
    r = np.array([0.01, 0.02, -0.01])  # only 3 samples
    with pytest.raises(ValueError, match="at least 30"):
        VaRCalculator.historical_simulation(r, portfolio_value=1000)


def test_historical_simulation_handles_all_positive_returns() -> None:
    """When no return is below the VaR threshold, CVaR should fall back to VaR (not NaN)."""
    r = np.full(100, 0.01)  # all +1% — there is no loss
    result = VaRCalculator.historical_simulation(r, portfolio_value=1_000)
    # All returns are +1%, so 5th percentile is also +1%; var = -(0.01) = -0.01.
    # Negative VaR is mathematically valid — it represents a *gain* not a loss.
    assert result.var_95 == pytest.approx(-0.01 * 1_000, rel=1e-9)
    # Crucially, no NaN/Inf in the result.
    assert np.isfinite(result.var_95)
    assert np.isfinite(result.cvar_95)
    assert np.isfinite(result.var_99)


def test_parametric_var_signs() -> None:
    r = _returns()
    result = VaRCalculator.parametric_var(r, portfolio_value=500_000, holding_period=1)
    assert result.method == "parametric"
    # Parametric VaR for ~zero-mean returns must be non-negative (loss).
    assert result.var_95 > 0
    assert result.var_99 > result.var_95


def test_holding_period_scales_var() -> None:
    r = _returns()
    one_day = VaRCalculator.historical_simulation(r, portfolio_value=1_000_000, holding_period=1)
    ten_day = VaRCalculator.historical_simulation(r, portfolio_value=1_000_000, holding_period=10)
    # 10-day VaR must be larger than 1-day VaR (sqrt(10) ≈ 3.16×).
    assert ten_day.var_95 > one_day.var_95
    ratio = ten_day.var_95 / one_day.var_95
    assert 3.0 < ratio < 3.3
