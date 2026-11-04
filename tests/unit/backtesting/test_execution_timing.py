"""Task 2: execution_timing — next_open (default) vs same_close."""


def _bars(n=30):
    return [
        {
            "instrument_id": "X",
            "timestamp": f"2024-01-{i + 1:02d}",
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 2_000_000,
        }
        for i in range(n)
    ]


class AlwaysBuy:
    """Signals a 1-share buy on every bar at bar close."""

    def __init__(self):
        self.ctx = None

    def set_context(self, ctx):
        self.ctx = ctx

    def reset(self):
        pass

    def on_bar(self, bar):
        from backtesting.types import OrderEvent, OrderSide

        return [
            OrderEvent(
                instrument_id="X", side=OrderSide.BUY, quantity=1,
                price=bar["close"], daily_volume=2_000_000,
            )
        ]


def test_same_close_fills_at_signal_bar_close():
    from backtesting.engine.simulator import BacktestSimulator

    bars = _bars()
    sim = BacktestSimulator(execution_timing="same_close")
    res = sim.run(AlwaysBuy(), data=bars)
    assert res.success, res.error
    fills = res.value.trades
    assert len(fills) == len(bars)
    for f, b in zip(fills, bars, strict=False):
        # fill price = bar close ± slippage (slippage small vs 1.0 bar step)
        assert abs(f.price - b["close"]) < 0.2, (f.price, b["close"])


def test_next_open_fills_at_next_bar_open():
    from backtesting.engine.simulator import BacktestSimulator

    bars = _bars()
    sim = BacktestSimulator(execution_timing="next_open")
    res = sim.run(AlwaysBuy(), data=bars)
    assert res.success, res.error
    fills = res.value.trades
    # last bar's signal has no next bar → dropped
    assert len(fills) == len(bars) - 1
    for f, b in zip(fills, bars[1:], strict=False):
        assert abs(f.price - b["open"]) < 0.2, (f.price, b["open"])
    assert res.value.metadata["execution_timing"] == "next_open"


def test_default_timing_is_next_open():
    from backtesting.engine.simulator import BacktestSimulator

    assert BacktestSimulator().execution_timing == "next_open"
