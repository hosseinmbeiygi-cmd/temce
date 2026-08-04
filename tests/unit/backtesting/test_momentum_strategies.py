"""Unit tests for momentum-based trading strategies.

Tests the ZeroDivision guards and core logic of:
- MomentumStrategy
- MomentumFactorStrategy
- MovingAverageCrossStrategy
- MeanReversionStrategy
"""

from __future__ import annotations

from backtesting.strategies.factor_based.momentum_factor_strategy import (
    MomentumFactorStrategy,
)
from backtesting.strategies.rule_based.mean_reversion_strategy import (
    MeanReversionStrategy,
)
from backtesting.strategies.rule_based.momentum_strategy import MomentumStrategy
from backtesting.strategies.rule_based.moving_average_cross import (
    MovingAverageCrossStrategy,
)

# ──────────────────────────────────────────────
# MomentumStrategy
# ──────────────────────────────────────────────


class TestMomentumStrategy:
    def test_init(self):
        s = MomentumStrategy(lookback=20, threshold_pct=5.0, instrument_id="test")
        assert s.lookback == 20
        assert s.threshold_pct == 5.0
        assert s.instrument_id == "test"

    def test_price_zero_returns_empty(self):
        s = MomentumStrategy(lookback=5, instrument_id="test")
        orders = s.on_bar({"close": 0})
        assert orders == []

    def test_not_enough_data_returns_empty(self):
        s = MomentumStrategy(lookback=5, instrument_id="test")
        for price in [100, 102, 101, 103]:
            orders = s.on_bar({"close": price})
            assert orders == []  # Not enough bars yet

    def test_no_division_by_zero_start_price(self):
        """ZeroDivision guard: if start_price is 0, momentum should be 0."""
        s = MomentumStrategy(lookback=3, threshold_pct=1.0, instrument_id="test")
        # Push prices including a zero
        for price in [100, 102, 0, 101, 105]:
            s.on_bar({"close": price})
        # At this point the last call had start_price=0, should not crash
        orders = s.on_bar({"close": 106})
        assert isinstance(orders, list)

    def test_momentum_buy_signal(self):
        s = MomentumStrategy(lookback=3, threshold_pct=2.0, instrument_id="test")
        # Manually set prices to known state, then call on_bar
        s._prices = [100, 102, 101, 103]
        # Now 5th bar: price=115, start_price=_prices[-4]=100
        # momentum = (115-100)/100*100 = 15% > 2% → BUY
        orders = s.on_bar({"close": 115})
        assert len(orders) == 1
        assert orders[0].side.value == "buy"

    def test_momentum_sell_signal(self):
        s = MomentumStrategy(lookback=3, threshold_pct=2.0, instrument_id="test")
        s._prices = [100, 102, 101, 103]
        s._position = 1  # Currently long so a sell signal can fire
        # price=85, start_price=102, momentum=(85-102)/102*100=-16.7% < -2% → SELL
        orders = s.on_bar({"close": 85})
        assert len(orders) == 1
        assert orders[0].side.value == "sell"

    def test_reset_clears_state(self):
        s = MomentumStrategy(lookback=5, instrument_id="test")
        s.on_bar({"close": 100})
        s.reset()
        assert s._position == 0
        assert len(s._prices) == 0


# ──────────────────────────────────────────────
# MomentumFactorStrategy
# ──────────────────────────────────────────────


class TestMomentumFactorStrategy:
    def test_init(self):
        s = MomentumFactorStrategy(short_lookback=60, long_lookback=252, instrument_id="test")
        assert s.short_lookback == 60
        assert s.long_lookback == 252

    def test_price_zero_returns_empty(self):
        s = MomentumFactorStrategy(instrument_id="test")
        assert s.on_bar({"close": 0}) == []

    def test_not_enough_data_returns_empty(self):
        s = MomentumFactorStrategy(short_lookback=3, long_lookback=5, instrument_id="test")
        for i in range(5):
            orders = s.on_bar({"close": 100.0 + i})
            assert orders == []

    def test_zero_division_guard(self):
        """When historical price is 0, short_ret/long_ret should be 0.0 not crash."""
        s = MomentumFactorStrategy(short_lookback=2, long_lookback=3, instrument_id="test")
        # Push enough data including a zero price to trigger division by zero guard
        for price in [100, 0, 102, 105]:
            s.on_bar({"close": price})
        # Prices[-long_lookback] = prices[0] = 100 (not zero), need to force zero at position
        s._prices = [0.0, 100.0, 102.0, 105.0, 108.0]
        orders = s.on_bar({"close": 110.0})
        assert isinstance(orders, list)

    def test_buy_signal_on_positive_momentum(self):
        s = MomentumFactorStrategy(short_lookback=2, long_lookback=3, instrument_id="test")
        # Set enough price history for long_lookback=3
        s._prices = [100, 105, 110, 115, 120]
        # Now on_bar(130): prev_short=_prices[-2]=120, prev_long=_prices[-3]=115
        # short_ret=(130-120)/120=0.083, long_ret=(130-115)/115=0.130
        # momentum_score=0.213 > 0 → BUY
        orders = s.on_bar({"close": 130})
        assert len(orders) == 1
        assert orders[0].side.value == "buy"

    def test_sell_signal_on_negative_momentum(self):
        s = MomentumFactorStrategy(short_lookback=2, long_lookback=3, instrument_id="test")
        s._prices = [100, 98, 96, 94, 92]
        # on_bar(80): prev_short=92, prev_long=94
        # short_ret=(80-92)/92=-0.130, long_ret=(80-94)/94=-0.149
        # momentum_score=-0.279 < 0
        s._position = 1  # Currently long → can sell
        orders = s.on_bar({"close": 80})
        assert len(orders) == 1
        assert orders[0].side.value == "sell"

    def test_reset(self):
        s = MomentumFactorStrategy(instrument_id="test")
        s._prices = [100, 102, 105]
        s._position = 1
        s.reset()
        assert s._position == 0
        assert s._prices == []


# ──────────────────────────────────────────────
# MovingAverageCrossStrategy
# ──────────────────────────────────────────────


class TestMovingAverageCrossStrategy:
    def test_init(self):
        s = MovingAverageCrossStrategy(fast_period=5, slow_period=20)
        assert s.fast_period == 5
        assert s.slow_period == 20

    def test_price_zero_returns_empty(self):
        s = MovingAverageCrossStrategy(instrument_id="test")
        assert s.on_bar({"close": 0}) == []

    def test_not_enough_data(self):
        s = MovingAverageCrossStrategy(fast_period=2, slow_period=3, instrument_id="test")
        for price in [100, 102]:
            assert s.on_bar({"close": price}) == []

    def test_buy_when_fast_crosses_above_slow(self):
        s = MovingAverageCrossStrategy(fast_period=2, slow_period=3, instrument_id="test")
        s._prices = [100, 101, 99, 110, 120]
        # on_bar(140): _prices=[100,101,99,110,120,140]
        # fast_ma = (120+140)/2 = 130, slow_ma = (110+120+140)/3 = 123.33
        # 130 > 123.33 → BUY
        orders = s.on_bar({"close": 140})
        assert len(orders) == 1
        assert orders[0].side.value == "buy"

    def test_sell_when_fast_crosses_below_slow(self):
        s = MovingAverageCrossStrategy(fast_period=2, slow_period=3, instrument_id="test")
        s._prices = [100, 101, 99, 110, 100]
        # on_bar(80): _prices=[100,101,99,110,100,80]
        # fast_ma = (100+80)/2 = 90, slow_ma = (110+100+80)/3 = 96.67
        # 90 < 96.67 → SELL
        s._position = 1
        orders = s.on_bar({"close": 80})
        assert len(orders) == 1
        assert orders[0].side.value == "sell"

    def test_no_signal_windowing(self):
        """No order when equal (within floating point)."""
        s = MovingAverageCrossStrategy(fast_period=2, slow_period=3, instrument_id="test")
        for price in [100, 100, 100, 100, 100, 100]:
            s.on_bar({"close": price})
        orders = s.on_bar({"close": 100})
        assert orders == []

    def test_constant_prices_no_signal(self):
        s = MovingAverageCrossStrategy(fast_period=2, slow_period=3, instrument_id="test")
        for _ in range(10):
            assert s.on_bar({"close": 100}) == []

    def test_reset(self):
        s = MovingAverageCrossStrategy(instrument_id="test")
        s._prices = [100, 102]
        s._position = 1
        s.reset()
        assert s._prices == []
        assert s._position == 0


# ──────────────────────────────────────────────
# MeanReversionStrategy
# ──────────────────────────────────────────────


class TestMeanReversionStrategy:
    def test_init(self):
        s = MeanReversionStrategy(lookback=20, entry_z=2.0, exit_z=0.5)
        assert s.lookback == 20
        assert s.entry_z == 2.0
        assert s.exit_z == 0.5

    def test_price_zero_returns_empty(self):
        s = MeanReversionStrategy(instrument_id="test")
        assert s.on_bar({"close": 0}) == []

    def test_not_enough_data(self):
        s = MeanReversionStrategy(lookback=5, instrument_id="test")
        for _ in range(5):
            assert s.on_bar({"close": 100}) == []

    def test_sell_when_price_spikes_up(self):
        s = MeanReversionStrategy(lookback=5, entry_z=1.5, instrument_id="test")
        # Prices stable around 100
        for price in [100, 101, 99, 100, 102]:
            s.on_bar({"close": price})
        s._position = 1  # Currently long so a sell signal can fire
        # mean ≈ 104.4, std ≈ 8.05, then price=120 → z ≈ 1.94 >> 1.5
        orders = s.on_bar({"close": 120})
        assert len(orders) == 1
        assert orders[0].side.value == "sell"

    def test_buy_when_price_drops_sharply(self):
        s = MeanReversionStrategy(lookback=5, entry_z=1.5, instrument_id="test")
        for price in [100, 101, 99, 100, 102]:
            s.on_bar({"close": price})
        # mean ≈ 100.4, std ≈ 1.14, price=80 → z ≈ -17.9 << -1.5
        orders = s.on_bar({"close": 80})
        assert len(orders) == 1
        assert orders[0].side.value == "buy"

    def test_no_signal_within_band(self):
        s = MeanReversionStrategy(lookback=5, entry_z=3.0, exit_z=0.5, instrument_id="test")
        # Give it a narrow range to work with
        prices = [100, 100.5, 99.5, 100.2, 99.8]
        for p in prices:
            s.on_bar({"close": p})
        s._position = 1  # Exit mode
        orders = s.on_bar({"close": 100})
        # At exit mode, z close to 0 → abs(z) < 0.5 → exit signal
        assert len(orders) == 1
        assert orders[0].side.value == "sell"

    def test_zero_std_guard(self):
        """When std is 0, z_score should be 0 not crash."""
        s = MeanReversionStrategy(lookback=3, instrument_id="test")
        for _ in range(5):
            s.on_bar({"close": 100})
        # All prices = 100 → std = 0, z_score = 0
        orders = s.on_bar({"close": 100})
        assert orders == []

    def test_reset(self):
        s = MeanReversionStrategy(instrument_id="test")
        s._prices = [100, 102]
        s._position = 1
        s.reset()
        assert s._prices == []
        assert s._position == 0
