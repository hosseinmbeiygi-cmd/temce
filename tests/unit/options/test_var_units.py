"""FIN-11: one unit contract for VaR inputs and outputs.

Inputs are decimal fractions (2% = ``0.02``); ``var_*`` are currency losses
and ``var_*_pct`` are percentages of the portfolio (2.5 = 2.5%). The previous
code documented percentages while doing decimal arithmetic, and the pct field
carried a fraction — a caller got either a 100x VaR or a mislabelled number.
"""

from __future__ import annotations

import numpy as np
import pytest

from domain.options.var_calculator import VaRCalculator


def _returns(n: int = 500, seed: int = 42) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.001, 0.02, n)


def test_historical_reports_currency_and_percent_consistently() -> None:
    result = VaRCalculator.historical_simulation(_returns(), portfolio_value=1_000_000_000)

    assert result.var_95 == pytest.approx(result.var_95_pct / 100.0 * result.portfolio_value)


def test_parametric_reports_currency_and_percent_consistently() -> None:
    result = VaRCalculator.parametric_var(_returns(), portfolio_value=1_000_000_000)

    assert result.var_95 == pytest.approx(result.var_95_pct / 100.0 * result.portfolio_value)
    # 2% daily sigma → one-day 95% VaR is a few percent, never hundreds.
    assert 1.0 < result.var_95_pct < 10.0


def test_monte_carlo_reports_currency_and_percent_consistently() -> None:
    result = VaRCalculator.monte_carlo_var(
        portfolio_value=1_000_000_000, mu=0.15, sigma=0.30, n_sims=5000
    )

    assert result.var_95 == pytest.approx(result.var_95_pct / 100.0 * result.portfolio_value)


def test_greeks_var_reports_percent_not_fraction() -> None:
    result = VaRCalculator.greeks_based_var(
        portfolio_delta=1000.0,
        portfolio_gamma=0.0,
        portfolio_vega=0.0,
        spot_price=10_000.0,
        spot_move_pct=0.02,
        vol_move_pct=0.10,
        portfolio_value=1_000_000_000.0,
    )

    # 1000 delta * 10,000 * 2% * 1.645 ≈ 329,000 → 0.0329% of 1e9
    assert result.var_95_pct == pytest.approx(0.0329, rel=1e-3)


def test_percent_scaled_returns_are_rejected() -> None:
    with pytest.raises(ValueError, match="percent"):
        VaRCalculator.historical_simulation(_returns() * 100, portfolio_value=1_000_000_000)
    with pytest.raises(ValueError, match="percent"):
        VaRCalculator.parametric_var(_returns() * 100, portfolio_value=1_000_000_000)


def test_percent_scaled_mu_sigma_is_rejected() -> None:
    with pytest.raises(ValueError, match="percent"):
        VaRCalculator.monte_carlo_var(portfolio_value=1_000_000_000, mu=15.0, sigma=30.0)


def test_non_finite_returns_are_rejected() -> None:
    bad = _returns()
    bad[0] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        VaRCalculator.historical_simulation(bad, portfolio_value=1_000_000_000)


def test_greeks_var_cvar_is_finite_normal_expected_shortfall() -> None:
    """CVaR must derive from the Gaussian ES ratio, never a magic multiplier."""
    result = VaRCalculator.greeks_based_var(
        portfolio_delta=1000.0,
        portfolio_gamma=2.0,
        portfolio_vega=5000.0,
        spot_price=10_000.0,
        spot_move_pct=0.02,
        vol_move_pct=0.10,
        portfolio_value=1_000_000_000.0,
    )

    assert np.isfinite(result.cvar_95)
    assert np.isfinite(result.cvar_99)
    assert result.cvar_95 == pytest.approx(result.var_95 * 1.25363, rel=1e-4)
    assert result.cvar_99 == pytest.approx(result.var_99 * 1.14676, rel=1e-4)
    assert result.cvar_95 >= result.var_95
    assert result.cvar_99 >= result.var_99
