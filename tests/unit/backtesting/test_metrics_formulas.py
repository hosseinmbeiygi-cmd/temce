"""Formula pins for Sharpe / max drawdown / profit factor (task 5).

These are reference computations, not implementation echoes: they encode the
annualisation and definitions the rest of the platform relies on.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
import pytest

from backtesting.metrics.performance import PerformanceMetrics
from backtesting.metrics.trade_metrics import TradeMetrics
from backtesting.types import BacktestResult, EquityPoint, FillEvent
from domain.common.enum_types import OrderSide


def _result(navs: list[float], trades: list[FillEvent] | None = None) -> BacktestResult:
    equity = [
        EquityPoint(timestamp=datetime(2026, 1, 1, tzinfo=UTC), nav=nav, cash=0.0, positions_value=0.0)
        for nav in navs
    ]
    return BacktestResult(strategy_name="t", initial_capital=navs[0], final_capital=navs[-1],
                          equity_curve=equity, trades=trades or [])


def test_sharpe_uses_annualized_mean_minus_risk_free_over_annualized_vol() -> None:
    navs = [100.0, 110.0, 99.0, 121.0]
    rf = 0.25
    metrics = PerformanceMetrics.compute(_result(navs), risk_free_rate=rf)

    returns = np.diff(navs) / np.array(navs[:-1])
    vol = np.std(returns) * math.sqrt(252)
    expected = (np.mean(returns) * 252 - rf) / vol

    assert metrics["volatility"] == pytest.approx(vol)
    assert metrics["sharpe_ratio"] == pytest.approx(expected)


def test_higher_risk_free_rate_lowers_sharpe() -> None:
    navs = [100.0, 102.0, 101.0, 104.0]
    zero_rf = PerformanceMetrics.compute(_result(navs), risk_free_rate=0.0)["sharpe_ratio"]
    high_rf = PerformanceMetrics.compute(_result(navs), risk_free_rate=0.30)["sharpe_ratio"]

    assert zero_rf > high_rf


def test_max_drawdown_is_peak_to_trough_percent() -> None:
    metrics = PerformanceMetrics.compute(_result([100.0, 110.0, 99.0, 121.0]))

    # peak 110 -> trough 99 = -10%
    assert metrics["max_drawdown"] == pytest.approx(-10.0)


def test_flat_nav_has_zero_sharpe_and_drawdown() -> None:
    metrics = PerformanceMetrics.compute(_result([100.0, 100.0, 100.0]))

    assert metrics["sharpe_ratio"] == 0.0
    assert metrics["max_drawdown"] == pytest.approx(0.0)


def test_profit_factor_all_winning_is_finite_not_zero() -> None:
    trades = [
        FillEvent(order_id="b", instrument_id="X", side=OrderSide.BUY, quantity=100, price=1000.0),
        FillEvent(order_id="s", instrument_id="X", side=OrderSide.SELL, quantity=100, price=1100.0),
    ]

    metrics = TradeMetrics.compute(_result([100.0, 110.0], trades))

    # No losing round trip → gross wins over a floor of 1.0, never 0.0/inf.
    assert metrics["profit_factor"] == pytest.approx(10_000.0)
