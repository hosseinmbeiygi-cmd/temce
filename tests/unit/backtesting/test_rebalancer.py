from __future__ import annotations

from backtesting.portfolio.rebalancer import (
    RebalanceCost,
    RebalanceFrequency,
    Rebalancer,
    RebalanceRule,
)


class TestRebalancer:
    def test_initial_state(self):
        r = Rebalancer(RebalanceRule())
        assert r.rebalance_count == 0

    def test_should_rebalance_by_frequency(self):
        r = Rebalancer(RebalanceRule(frequency=RebalanceFrequency.DAILY))
        should, reason = r.should_rebalance({"A": 0.5}, {"A": 0.5})
        assert should
        assert "daily" in reason

    def test_should_rebalance_by_threshold(self):
        r = Rebalancer(RebalanceRule(threshold_pct=5.0, frequency_days=100))
        should, reason = r.should_rebalance({"A": 0.6}, {"A": 0.5})
        assert should
        assert "threshold" in reason

    def test_should_not_rebalance(self):
        r = Rebalancer(RebalanceRule(threshold_pct=50.0, frequency_days=100))
        should, reason = r.should_rebalance({"A": 0.5}, {"A": 0.5})
        assert not should

    def test_compute_trades(self):
        r = Rebalancer(RebalanceRule())
        current = {"A": 100_000_000, "B": 200_000_000}
        target = {"A": 0.5, "B": 0.5}
        result = r.compute_trades(current, target, 1_000_000_000)
        assert len(result.trades) > 0
        assert result.total_cost > 0

    def test_compute_trades_min_trade_filter(self):
        r = Rebalancer(RebalanceRule(min_trade_value=10_000_000_000))
        current = {"A": 100_000_000, "B": 200_000_000}
        target = {"A": 0.5, "B": 0.5}
        result = r.compute_trades(current, target, 1_000_000_000)
        assert len(result.trades) == 0

    def test_rebalance_full_flow(self):
        r = Rebalancer(RebalanceRule(frequency=RebalanceFrequency.DAILY))
        result = r.rebalance({"A": 100_000_000}, {"A": 0.5, "B": 0.5}, 1_000_000_000)
        assert result is not None
        assert result.triggered_by != ""
        assert r.rebalance_count == 1

    def test_rebalance_not_needed(self):
        r = Rebalancer(RebalanceRule(threshold_pct=50.0, frequency_days=100))
        result = r.rebalance({"A": 0.5}, {"A": 0.5}, 1_000_000_000)
        assert result is None

    def test_cost_calculation(self):
        cost = RebalanceCost(commission_pct=0.0035, slippage_bps=10, tax_pct=0.0005)
        total = cost.total_cost_pct()
        assert total > 0

    def test_turnover_limit(self):
        r = Rebalancer(RebalanceRule(max_turnover_pct=1.0, threshold_pct=1.0))
        current = {"A": 0}
        target = {"A": 1.0}
        result = r.compute_trades(current, target, 1_000_000_000)
        assert result.turnover_pct <= 1.0

    def test_get_history(self):
        r = Rebalancer(RebalanceRule(frequency=RebalanceFrequency.DAILY))
        r.rebalance({"A": 100_000_000}, {"A": 0.5, "B": 0.5}, 1_000_000_000)
        history = r.get_history()
        assert len(history) == 1

    def test_get_total_costs(self):
        r = Rebalancer(RebalanceRule(frequency=RebalanceFrequency.DAILY))
        r.rebalance({"A": 100_000_000}, {"A": 0.5, "B": 0.5}, 1_000_000_000)
        assert r.get_total_costs() > 0

    def test_reset(self):
        r = Rebalancer(RebalanceRule(frequency=RebalanceFrequency.DAILY))
        r.rebalance({"A": 100_000_000}, {"A": 0.5, "B": 0.5}, 1_000_000_000)
        r.reset()
        assert r.rebalance_count == 0
        assert r.get_total_costs() == 0
