"""Verify BacktestSimulator result type and attributes."""


from backtesting.engine.simulator import BacktestSimulator
from backtesting.strategies.base import BaseStrategy
from backtesting.types import OrderEvent
from domain.common.enum_types import OrderSide


class Simple(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.c = 0

    def on_bar(self, bar):
        self.c += 1
        p = bar.get("close", 0)
        if self.c == 5:
            return [OrderEvent(instrument_id="T", side=OrderSide.BUY, quantity=1, price=p)]
        if self.c == 45:
            return [OrderEvent(instrument_id="T", side=OrderSide.SELL, quantity=1, price=p)]
        return []

    def reset(self):
        super().reset()
        self.c = 0


def _make_bars(count: int = 50):
    bars = []
    price = 1000.0
    for i in range(count):
        price = max(1.0, price * (1 + (i - count / 2) * 0.001))
        bars.append(
            {
                "instrument_id": "T",
                "timestamp": f"2023-01-01T00:00:00.{i:03}",
                "open": price * 0.99,
                "high": price * 1.01,
                "low": price * 0.98,
                "close": price,
                "volume": 1000,
            }
        )
    return bars


def test_result_type():
    bars = _make_bars(50)
    sim = BacktestSimulator()
    result = sim.run(Simple(), initial_capital=1e7, data=bars)

    print("type:", type(result).__name__)
    print("success:", result.success)

    assert result.success, f"Backtest failed: {getattr(result, 'error', 'unknown error')}"
    r = result.value
    assert r is not None, "Result value should not be None on success"

    print("data type:", type(r).__name__)
    print("attrs:", [a for a in dir(r) if not a.startswith("_")])
    print("total_return_pct:", r.total_return_pct)
    print("max_drawdown:", r.max_drawdown)
    print("equity_curve type:", type(r.equity_curve).__name__, "len:", len(r.equity_curve))
    if r.equity_curve:
        print("equity[0]:", r.equity_curve[0])
