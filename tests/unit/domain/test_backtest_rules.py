from __future__ import annotations


def test_backtest_rule_valid_dates():
    from domain.backtest.rules import BacktestDateRule

    rule = BacktestDateRule()
    assert rule.validate(start_date="2024-01-01", end_date="2024-12-31") is True


def test_backtest_rule_invalid_dates():
    from domain.backtest.rules import BacktestDateRule

    rule = BacktestDateRule()
    assert rule.validate(start_date="2024-12-31", end_date="2024-01-01") is False


def test_backtest_rule_min_capital():
    from domain.backtest.rules import BacktestCapitalRule

    rule = BacktestCapitalRule(min_capital=100_000_000)
    assert rule.validate(initial_capital=1_000_000_000) is True
    assert rule.validate(initial_capital=10_000) is False


def test_backtest_rule_max_symbols():
    from domain.backtest.rules import BacktestSymbolRule

    rule = BacktestSymbolRule(max_symbols=10)
    assert rule.validate(symbols=["فولاد", "فملی"]) is True
    assert rule.validate(symbols=[f"sym_{i}" for i in range(20)]) is False


def test_backtest_rule_timeframe():
    from domain.backtest.rules import BacktestTimeframeRule

    rule = BacktestTimeframeRule(allowed_timeframes=["1d", "1h"])
    assert rule.validate(timeframe="1d") is True
    assert rule.validate(timeframe="1m") is False
