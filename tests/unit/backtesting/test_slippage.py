from __future__ import annotations

import pytest

from backtesting.constants import SlippageMode
from backtesting.engine.slippage import SlippageModel


def test_slippage_model_fixed():
    """FIXED mode: slippage = price * (fixed_bps / 10000)."""
    model = SlippageModel(mode=SlippageMode.FIXED, fixed_bps=10.0)
    slippage = model.compute_slippage(price=15000, order_size=1000)
    expected = 15000 * (10.0 / 10000)
    assert slippage == pytest.approx(expected)


def test_slippage_model_none():
    """NONE mode: always 0."""
    model = SlippageModel(mode=SlippageMode.NONE)
    assert model.compute_slippage(price=15000) == 0.0


def test_slippage_negative_bps():
    """Negative fixed_bps produces negative slippage."""
    model = SlippageModel(mode=SlippageMode.FIXED, fixed_bps=-5.0)
    slippage = model.compute_slippage(price=15000)
    assert slippage < 0


def test_slippage_percent_mode():
    """PERCENT mode: slippage = price * (fixed_bps / 10000)."""
    model = SlippageModel(mode=SlippageMode.PERCENT, fixed_bps=10.0)
    slippage = model.compute_slippage(price=15000)
    assert slippage == pytest.approx(15000 * 0.001)


def test_slippage_volume_based():
    """VOLUME_BASED mode adds volume impact."""
    model = SlippageModel(mode=SlippageMode.VOLUME_BASED, fixed_bps=10.0, volume_impact_pct=0.1)
    slippage = model.compute_slippage(price=15000, order_size=1000, adv=5000)
    fixed = 15000 * (10.0 / 10000)
    volume_impact = 15000 * (1000 / 5000) * 0.1
    assert slippage == pytest.approx(fixed + volume_impact)


def test_get_execution_price_buy():
    """Buy price = base price + slippage."""
    model = SlippageModel(mode=SlippageMode.FIXED, fixed_bps=10.0)
    exec_price = model.get_execution_price(price=15000, side="buy")
    assert exec_price > 15000


def test_get_execution_price_sell():
    """Sell price = base price - slippage."""
    model = SlippageModel(mode=SlippageMode.FIXED, fixed_bps=10.0)
    exec_price = model.get_execution_price(price=15000, side="sell")
    assert exec_price < 15000


def test_get_execution_price_with_volatility():
    """Volatility adds to slippage regardless of mode."""
    model = SlippageModel(mode=SlippageMode.FIXED, fixed_bps=10.0)
    with_vol = model.get_execution_price(price=15000, side="buy", volatility=0.02)
    without_vol = model.get_execution_price(price=15000, side="buy")
    assert with_vol > without_vol
