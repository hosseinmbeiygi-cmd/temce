"""Unit tests for FxCostModel — dynamic FX spread for backtesting."""

from __future__ import annotations

from backtesting.costs.fx_costs import (
    BASE_SPREAD_PCT,
    MAX_SPREAD_PCT,
    MIN_SPREAD_PCT,
    VOLATILITY_MULTIPLIER,
    FxCostModel,
)


class TestFxCostModelEffectiveSpread:
    """Test FxCostModel.effective_spread() dynamic spread calculation."""

    def test_base_spread_with_no_volatility(self):
        """Spread should equal base when volatility is zero."""
        model = FxCostModel()
        spread = model.effective_spread(recent_volatility=0.0)
        assert spread == BASE_SPREAD_PCT

    def test_spread_increases_with_volatility(self):
        """Spread should increase as volatility increases."""
        model = FxCostModel()
        spread_low = model.effective_spread(recent_volatility=0.01)
        spread_high = model.effective_spread(recent_volatility=0.05)
        assert spread_high > spread_low

    def test_spread_formula(self):
        """Spread should follow: base × (1 + volatility × multiplier)."""
        model = FxCostModel()
        volatility = 0.02
        expected = BASE_SPREAD_PCT * (1 + volatility * VOLATILITY_MULTIPLIER)
        actual = model.effective_spread(recent_volatility=volatility)
        assert abs(actual - expected) < 1e-10

    def test_spread_clamped_to_max(self):
        """Spread should not exceed MAX_SPREAD_PCT."""
        model = FxCostModel()
        spread = model.effective_spread(recent_volatility=1.0)  # extreme
        assert spread <= MAX_SPREAD_PCT

    def test_spread_clamped_to_min(self):
        """Spread should not go below MIN_SPREAD_PCT."""
        model = FxCostModel()
        spread = model.effective_spread(recent_volatility=-1.0)  # negative
        assert spread >= MIN_SPREAD_PCT


class TestFxCostModelCompute:
    """Test FxCostModel.compute() cost calculation."""

    def test_buy_cost_positive(self):
        """Buy cost should be positive."""
        model = FxCostModel()
        cost = model.compute("buy", price=200500, recent_volatility=0.02)
        assert cost > 0

    def test_sell_cost_positive(self):
        """Sell cost should be positive."""
        model = FxCostModel()
        cost = model.compute("sell", price=200500, recent_volatility=0.02)
        assert cost > 0

    def test_buy_cost_equals_sell_cost(self):
        """Buy and sell costs should be equal (symmetric spread)."""
        model = FxCostModel()
        buy = model.compute("buy", price=200500, recent_volatility=0.02)
        sell = model.compute("sell", price=200500, recent_volatility=0.02)
        assert abs(buy - sell) < 1e-10

    def test_cost_increases_with_volatility(self):
        """Cost should increase with higher volatility."""
        model = FxCostModel()
        cost_low = model.compute("buy", price=200500, recent_volatility=0.01)
        cost_high = model.compute("buy", price=200500, recent_volatility=0.05)
        assert cost_high > cost_low

    def test_cost_proportional_to_price(self):
        """Cost should be proportional to price."""
        model = FxCostModel()
        cost_100k = model.compute("buy", price=100000, recent_volatility=0.02)
        cost_200k = model.compute("buy", price=200000, recent_volatility=0.02)
        assert abs(cost_200k / cost_100k - 2.0) < 1e-10

    def test_case_insensitive_side(self):
        """Side should be case-insensitive."""
        model = FxCostModel()
        cost_buy = model.compute("BUY", price=200500)
        cost_buy_lower = model.compute("buy", price=200500)
        assert abs(cost_buy - cost_buy_lower) < 1e-10


class TestFxCostModelAdjustedPrice:
    """Test FxCostModel.adjusted_price() execution price."""

    def test_buy_adjusted_price_higher(self):
        """Buy adjusted price should be higher than mid price."""
        model = FxCostModel()
        mid = 200500
        adj = model.adjusted_price("buy", mid, recent_volatility=0.02)
        assert adj > mid

    def test_sell_adjusted_price_lower(self):
        """Sell adjusted price should be lower than mid price."""
        model = FxCostModel()
        mid = 200500
        adj = model.adjusted_price("sell", mid, recent_volatility=0.02)
        assert adj < mid

    def test_adjusted_price_spread_symmetry(self):
        """Buy and sell adjusted prices should be symmetric around mid."""
        model = FxCostModel()
        mid = 200500
        buy_adj = model.adjusted_price("buy", mid, recent_volatility=0.02)
        sell_adj = model.adjusted_price("sell", mid, recent_volatility=0.02)
        avg = (buy_adj + sell_adj) / 2
        assert abs(avg - mid) < 1e-10


class TestFxCostModelRoundTrip:
    """Test FxCostModel.round_trip_cost() total cost."""

    def test_round_trip_cost_positive(self):
        """Round-trip cost should be positive."""
        model = FxCostModel()
        cost = model.round_trip_cost(200500, 201000, recent_volatility=0.02)
        assert cost > 0

    def test_round_trip_cost_equals_buy_plus_sell(self):
        """Round-trip cost should equal buy + sell costs."""
        model = FxCostModel()
        rt = model.round_trip_cost(200500, 201000, recent_volatility=0.02)
        buy = model.buy_cost(200500, recent_volatility=0.02)
        sell = model.sell_cost(201000, recent_volatility=0.02)
        assert abs(rt - (buy + sell)) < 1e-10


class TestFxConstants:
    """Test FX cost model constants."""

    def test_base_spread_reasonable(self):
        """Base spread should be reasonable for FX."""
        assert 0.001 <= BASE_SPREAD_PCT <= 0.01  # 0.1% to 1%

    def test_volatility_multiplier_positive(self):
        """Volatility multiplier should be positive."""
        assert VOLATILITY_MULTIPLIER > 0

    def test_max_spread_greater_than_base(self):
        """Max spread should be greater than base."""
        assert MAX_SPREAD_PCT > BASE_SPREAD_PCT

    def test_min_spread_less_than_base(self):
        """Min spread should be less than base."""
        assert MIN_SPREAD_PCT < BASE_SPREAD_PCT
