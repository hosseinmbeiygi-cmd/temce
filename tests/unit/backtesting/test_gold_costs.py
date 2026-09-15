"""Unit tests for GoldCostModel — gold spread-based pricing."""

from __future__ import annotations

from backtesting.costs.gold_costs import (
    BASE_SPREAD_PCT,
    MAX_SPREAD_PCT,
    MIN_SPREAD_PCT,
    GoldCostModel,
)


class TestGoldCostModelCompute:
    """Test GoldCostModel.compute() cost calculation."""

    def test_buy_cost_positive(self):
        model = GoldCostModel()
        cost = model.compute("buy", price=214000000)
        assert cost > 0

    def test_sell_cost_positive(self):
        model = GoldCostModel()
        cost = model.compute("sell", price=214000000)
        assert cost > 0

    def test_buy_cost_equals_sell_cost(self):
        model = GoldCostModel()
        buy = model.compute("buy", price=214000000)
        sell = model.compute("sell", price=214000000)
        assert abs(buy - sell) < 1e-10

    def test_cost_proportional_to_price(self):
        model = GoldCostModel()
        cost_100m = model.compute("buy", price=100000000)
        cost_200m = model.compute("buy", price=200000000)
        assert abs(cost_200m / cost_100m - 2.0) < 1e-10

    def test_case_insensitive_side(self):
        model = GoldCostModel()
        cost_buy = model.compute("BUY", price=214000000)
        cost_buy_lower = model.compute("buy", price=214000000)
        assert abs(cost_buy - cost_buy_lower) < 1e-10


class TestGoldCostModelAdjustedPrice:
    """Test GoldCostModel.adjusted_price() execution price."""

    def test_buy_adjusted_price_higher(self):
        model = GoldCostModel()
        mid = 214000000
        adj = model.adjusted_price("buy", mid)
        assert adj > mid

    def test_sell_adjusted_price_lower(self):
        model = GoldCostModel()
        mid = 214000000
        adj = model.adjusted_price("sell", mid)
        assert adj < mid

    def test_adjusted_price_spread_symmetry(self):
        model = GoldCostModel()
        mid = 214000000
        buy_adj = model.adjusted_price("buy", mid)
        sell_adj = model.adjusted_price("sell", mid)
        avg = (buy_adj + sell_adj) / 2
        assert abs(avg - mid) < 1e-10


class TestGoldCostModelRoundTrip:
    """Test GoldCostModel.round_trip_cost() total cost."""

    def test_round_trip_cost_positive(self):
        model = GoldCostModel()
        cost = model.round_trip_cost(214000000, 215000000)
        assert cost > 0

    def test_round_trip_cost_equals_buy_plus_sell(self):
        model = GoldCostModel()
        rt = model.round_trip_cost(214000000, 215000000)
        buy = model.buy_cost(214000000)
        sell = model.sell_cost(215000000)
        assert abs(rt - (buy + sell)) < 1e-10


class TestGoldConstants:
    """Test gold cost model constants."""

    def test_base_spread_reasonable(self):
        assert 0.001 <= BASE_SPREAD_PCT <= 0.01

    def test_max_spread_greater_than_base(self):
        assert MAX_SPREAD_PCT > BASE_SPREAD_PCT

    def test_min_spread_less_than_base(self):
        assert MIN_SPREAD_PCT < BASE_SPREAD_PCT
