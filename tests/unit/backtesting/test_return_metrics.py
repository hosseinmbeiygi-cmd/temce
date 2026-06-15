from __future__ import annotations

import pytest


def test_total_return():
    from backtesting.metrics import ReturnMetrics

    metrics = ReturnMetrics()
    result = metrics.calculate_total_return(initial_capital=1_000_000_000, final_value=1_250_000_000)
    assert result == 25.0


def test_annualized_return():
    from backtesting.metrics import ReturnMetrics

    metrics = ReturnMetrics()
    result = metrics.calculate_annualized_return(total_return_pct=25.0, days=365)
    assert result == pytest.approx(25.0, rel=0.01)


def test_sharpe_ratio():
    from backtesting.metrics import ReturnMetrics

    metrics = ReturnMetrics()
    returns = [0.01, 0.02, -0.01, 0.015, -0.005, 0.03, 0.01, -0.02, 0.025, 0.005]
    sharpe = metrics.calculate_sharpe_ratio(returns, risk_free_rate=0.0)
    assert sharpe is not None


def test_max_drawdown():
    from backtesting.metrics import ReturnMetrics

    metrics = ReturnMetrics()
    equity = [100, 110, 105, 120, 115, 125, 130, 120, 140, 135]
    dd = metrics.calculate_max_drawdown(equity)
    assert dd < 0
    assert dd >= -20


def test_sortino_ratio():
    from backtesting.metrics import ReturnMetrics

    metrics = ReturnMetrics()
    returns = [0.01, 0.02, -0.01, 0.015, -0.005, 0.03, 0.01, -0.02, 0.025, 0.005]
    sortino = metrics.calculate_sortino_ratio(returns, risk_free_rate=0.0)
    assert sortino is not None
