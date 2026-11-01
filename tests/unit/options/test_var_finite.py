"""FIN: VaR/CVaR must never return NaN/inf (report 2.6 and task 4).

* All-positive return windows (strong uptrend) used to produce
  ``np.mean([]) = nan`` for CVaR in the original implementation.
* ``NaN`` inputs bypassed every range check (``nan > 1.0`` is False) and
  poisoned the JSON payload.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from domain.options.var_calculator import VaRCalculator


def _all_positive_returns(n: int = 200) -> np.ndarray:
    rng = np.random.default_rng(7)
    return np.abs(rng.normal(0.004, 0.002, n))


@pytest.mark.parametrize(
    "method",
    [
        VaRCalculator.historical_simulation,
        VaRCalculator.parametric_var,
    ],
)
def test_cvar_is_finite_in_strong_uptrend(method) -> None:
    result = method(_all_positive_returns(), portfolio_value=1_000_000_000.0)

    for name in ("var_95", "var_99", "cvar_95", "cvar_99", "var_95_pct", "var_99_pct"):
        value = getattr(result, name)
        assert math.isfinite(value), f"{name} is not finite: {value!r}"
    json.dumps(result.__dict__, allow_nan=False)


def test_monte_carlo_cvar_is_finite() -> None:
    result = VaRCalculator.monte_carlo_var(
        portfolio_value=1_000_000_000.0, mu=0.15, sigma=0.30, n_sims=2_000
    )
    json.dumps(result.__dict__, allow_nan=False)
    assert math.isfinite(result.cvar_95) and math.isfinite(result.cvar_99)


def test_nan_portfolio_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        VaRCalculator.historical_simulation(_all_positive_returns(), portfolio_value=float("nan"))


def test_nan_monte_carlo_inputs_are_rejected() -> None:
    """NaN bypasses ``mu > 1.0`` checks, so it needs an explicit guard."""
    with pytest.raises(ValueError, match="non-finite"):
        VaRCalculator.monte_carlo_var(portfolio_value=1e9, mu=float("nan"), sigma=0.3)


def test_infinite_greeks_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        VaRCalculator.greeks_based_var(
            portfolio_delta=float("inf"),
            portfolio_gamma=0.0,
            portfolio_vega=0.0,
            spot_price=10_000.0,
            spot_move_pct=0.02,
            vol_move_pct=0.1,
            portfolio_value=1e9,
        )


def test_overflowing_greeks_result_is_rejected_not_serialised_as_inf() -> None:
    with pytest.raises(ValueError, match="overflowed"):
        VaRCalculator.greeks_based_var(
            portfolio_delta=1e300,
            portfolio_gamma=0.0,
            portfolio_vega=0.0,
            spot_price=1e300,
            spot_move_pct=0.5,
            vol_move_pct=0.0,
            portfolio_value=1e9,
        )
