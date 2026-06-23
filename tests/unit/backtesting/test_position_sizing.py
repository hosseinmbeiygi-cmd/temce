from __future__ import annotations

import pytest


def test_fixed_position_sizing():
    from backtesting.sizing import PositionSizer

    sizer = PositionSizer(method="fixed", value=100_000_000)
    size = sizer.calculate(capital=1_000_000_000, price=15000)
    assert size == pytest.approx(6666.67, rel=0.1)


def test_percent_position_sizing():
    from backtesting.sizing import PositionSizer

    sizer = PositionSizer(method="percent", value=10.0)
    size = sizer.calculate(capital=1_000_000_000, price=15000)
    expected = (1_000_000_000 * 0.10) / 15000
    assert size == pytest.approx(expected, rel=0.01)


def test_kelly_criterion_sizing():
    from backtesting.sizing import PositionSizer

    sizer = PositionSizer(method="kelly", value=0.5)
    size = sizer.calculate(capital=1_000_000_000, price=15000, win_rate=0.6, avg_win=0.1, avg_loss=0.05)
    expected = (1_000_000_000 * 0.5) / 15000  # clamped by value=0.5
    assert size == pytest.approx(expected, rel=0.01)


def test_kelly_criterion_exact():
    """Test Kelly formula with small edge where cap is not hit."""
    from backtesting.sizing import PositionSizer

    sizer = PositionSizer(method="kelly", value=1.0)
    # f* = (0.5*0.5 - 0.5*0.4) / (0.5*0.4) = 0.05/0.20 = 0.25
    size = sizer.calculate(capital=1_000_000_000, price=15000, win_rate=0.5, avg_win=0.5, avg_loss=0.4)
    expected = (1_000_000_000 * 0.25) / 15000  # 250_000_000 / 15000
    assert size == pytest.approx(expected, rel=0.01)


def test_risk_based_sizing():
    from backtesting.sizing import PositionSizer

    sizer = PositionSizer(method="risk_based", value=2.0)
    size = sizer.calculate(capital=1_000_000_000, price=15000, stop_loss_pct=2.0)
    expected = (1_000_000_000 * 0.02) / (15000 * 0.02)
    assert size == pytest.approx(expected, rel=0.01)

