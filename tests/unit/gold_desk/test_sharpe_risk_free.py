"""Sharpe on the strategy NAV must use the domestic risk-free rate.

Audit FIN-06. ``_annualized_sharpe`` subtracted nothing, so with the domain's
30% risk-free rate a 20%/yr strategy reported ~0.8 instead of a negative
excess-return ratio.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.gold_desk.backtest_runner import TRADING_DAYS_PER_YEAR, _annualized_sharpe
from src.gold_desk.black76 import IRAN_RISK_FREE_RATE


def test_default_uses_the_domestic_risk_free_rate() -> None:
    nav = np.array([100.0, 101.0, 100.5, 102.0, 103.0])
    returns = np.diff(nav) / nav[:-1]
    excess = returns - IRAN_RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
    expected = float(np.sqrt(TRADING_DAYS_PER_YEAR) * np.mean(excess) / np.std(excess))

    assert _annualized_sharpe(nav) == pytest.approx(expected)


def test_zero_rate_overstates_a_strong_series() -> None:
    nav = np.array([100.0, 100.2, 100.4, 100.7, 101.0])

    assert _annualized_sharpe(nav, risk_free_annual=0.0) > _annualized_sharpe(nav)


def test_flat_nav_is_zero_not_infinity() -> None:
    assert _annualized_sharpe(np.array([100.0, 100.0, 100.0])) == 0.0
