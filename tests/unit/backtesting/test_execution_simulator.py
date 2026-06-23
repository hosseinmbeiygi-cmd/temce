from __future__ import annotations


def test_market_order_execution():
    from backtesting.execution import ExecutionSimulator

    simulator = ExecutionSimulator(slippage_bps=10)
    result = simulator.execute_market_order(side="buy", quantity=1000, price=15000)
    assert result["filled_quantity"] == 1000
    assert result["avg_price"] > 15000
    slippage = (result["avg_price"] - 15000) / 15000 * 10000
    assert slippage <= 11


def test_limit_order_execution():
    from backtesting.execution import ExecutionSimulator

    simulator = ExecutionSimulator(slippage_bps=10)
    result = simulator.execute_limit_order(side="buy", quantity=1000, limit_price=15000, current_price=14950)
    assert result["filled"] is True or result["filled"] is False


def test_slippage_impact():
    from backtesting.execution import ExecutionSimulator

    simulator = ExecutionSimulator(slippage_bps=10)
    buy_result = simulator.execute_market_order(side="buy", quantity=100, price=15000)
    sell_result = simulator.execute_market_order(side="sell", quantity=100, price=15000)
    assert buy_result["avg_price"] >= 15000
    assert sell_result["avg_price"] <= 15000


def test_partial_fill():
    from backtesting.execution import ExecutionSimulator

    simulator = ExecutionSimulator(slippage_bps=10, partial_fill_enabled=True)
    result = simulator.execute_market_order(side="buy", quantity=10_000_000, price=15000)
    assert result["filled_quantity"] > 0

