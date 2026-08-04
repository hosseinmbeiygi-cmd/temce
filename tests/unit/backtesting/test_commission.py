from __future__ import annotations


def test_commission_calculation():
    from backtesting.commission import CommissionModel

    model = CommissionModel(commission_pct=0.0035)
    commission = model.calculate(trade_value=1_000_000_000)
    assert commission == 3_500_000


def test_commission_with_minimum():
    from backtesting.commission import CommissionModel

    model = CommissionModel(commission_pct=0.0035, min_commission=1_000)
    small = model.calculate(trade_value=100_000)
    assert small >= 1_000


def test_commission_with_maximum():
    from backtesting.commission import CommissionModel

    model = CommissionModel(commission_pct=0.0035, max_commission=10_000_000)
    large = model.calculate(trade_value=10_000_000_000)
    assert large <= 10_000_000


def test_commission_zero_value():
    from backtesting.commission import CommissionModel

    model = CommissionModel(commission_pct=0.0035)
    assert model.calculate(trade_value=0) == 0
