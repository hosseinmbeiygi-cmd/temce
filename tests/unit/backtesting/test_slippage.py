from __future__ import annotations


def test_slippage_model():
    from backtesting.slippage import SlippageModel

    model = SlippageModel(slippage_bps=10)
    slippage = model.calculate(price=15000, quantity=1000)
    expected_slippage = 15000 * 1000 * (10 / 10000)
    assert slippage == expected_slippage


def test_slippage_percentage():
    from backtesting.slippage import SlippageModel

    model = SlippageModel(slippage_bps=10)
    pct = model.slippage_pct()
    assert pct == 0.001


def test_slippage_negative():
    from backtesting.slippage import SlippageModel

    model = SlippageModel(slippage_bps=-5)
    slippage = model.calculate(price=15000, quantity=1000)
    assert slippage < 0


def test_adjusted_price():
    from backtesting.slippage import SlippageModel

    model = SlippageModel(slippage_bps=10)
    buy_price = model.adjust_price(price=15000, side="buy")
    sell_price = model.adjust_price(price=15000, side="sell")
    assert buy_price > 15000
    assert sell_price < 15000

