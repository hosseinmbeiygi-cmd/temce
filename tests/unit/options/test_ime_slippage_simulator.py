"""Tests for the MC slippage simulator (سند §4.3 + §7.1).

Covers the slippage distribution sampler, the conservative-tail hard block,
and the NetEdge MC loop for the Statistical Acceptance Gate.
"""

from __future__ import annotations

from services.ime_slippage_simulator import (
    BidAskObservation,
    accept_reject_block,
    sample_slippage,
    simulate_netedge_mc,
)


def _make_history(n: int = 100, spread_mean: float = 0.005, depth_mean: int = 500) -> list[BidAskObservation]:
    return [
        BidAskObservation(
            spread_pct=spread_mean * (1 + 0.1 * (i % 3 - 1)), depth=int(depth_mean * (1 + 0.05 * (i % 5 - 2)))
        )
        for i in range(n)
    ]


class TestSampleSlippage:
    def test_empty_history_returns_zero(self):
        d = sample_slippage([], order_size=10, avg_volume=1000, volatility=0.2, eta=0.1, gamma=0.05)
        assert d.mean == 0.0
        assert d.n_scenarios == 0

    def test_distribution_is_monotonic(self):
        d = sample_slippage(_make_history(), 100, 5000, 0.2, 0.1, 0.05, n_scenarios=2000, seed=1)
        assert d.p5 <= d.p50 <= d.p95
        assert d.p95 > d.p5  # real spread, not degenerate

    def test_larger_order_increases_mean(self):
        small = sample_slippage(_make_history(), 10, 5000, 0.2, 0.1, 0.05, n_scenarios=1000, seed=2)
        large = sample_slippage(_make_history(), 1000, 5000, 0.2, 0.1, 0.05, n_scenarios=1000, seed=2)
        assert large.mean > small.mean

    def test_n_scenarios_match_request(self):
        d = sample_slippage(_make_history(), 100, 5000, 0.2, 0.1, 0.05, n_scenarios=300, seed=3)
        assert d.n_scenarios == 300

    def test_reproducible_with_seed(self):
        h = _make_history()
        d1 = sample_slippage(h, 100, 5000, 0.2, 0.1, 0.05, n_scenarios=500, seed=42)
        d2 = sample_slippage(h, 100, 5000, 0.2, 0.1, 0.05, n_scenarios=500, seed=42)
        assert d1.mean == d2.mean
        assert d1.p95 == d2.p95


class TestAcceptRejectBlock:
    def test_passes_when_far_from_threshold(self):
        d = sample_slippage(_make_history(), 100, 5000, 0.2, 0.1, 0.05, n_scenarios=500, seed=5)
        ok, reason = accept_reject_block(net_edge=500.0, slippage_dist=d, gross_edge=1000.0)
        assert ok
        assert "passes" in reason

    def test_blocks_negative_net_edge(self):
        d = sample_slippage(_make_history(), 100, 5000, 0.2, 0.1, 0.05, n_scenarios=500, seed=6)
        ok, reason = accept_reject_block(net_edge=-10.0, slippage_dist=d, gross_edge=1000.0)
        assert not ok
        assert "net_edge" in reason

    def test_blocks_high_p95_slippage(self):
        # Force extreme slippage: order 10x avg volume, high vol & impact coefs
        d = sample_slippage(_make_history(), 10_000, 100, 5.0, 5.0, 5.0, n_scenarios=500, seed=7)
        # gross=100, slippage from AC ≈ 5*5*√100 + 5*100 ≈ 250+500 = 750, p95 > 50
        ok, reason = accept_reject_block(net_edge=10.0, slippage_dist=d, gross_edge=100.0)
        assert not ok
        assert "p95" in reason

    def test_zero_gross_edge_trivially_passes(self):
        d = sample_slippage(_make_history(), 100, 5000, 0.2, 0.1, 0.05, n_scenarios=500, seed=8)
        ok, reason = accept_reject_block(net_edge=0.0, slippage_dist=d, gross_edge=0.0)
        assert ok
        assert "no gross" in reason


class TestSimulateNetedgeMC:
    def test_keys_present(self):
        result = simulate_netedge_mc(
            _make_history(),
            gross_edge=1000.0,
            commission=50.0,
            market_impact=20.0,
            latency_buffer=10.0,
            order_size=100,
            avg_volume=5000,
            volatility=0.2,
            eta=0.1,
            gamma=0.05,
            n_scenarios=500,
            seed=10,
        )
        assert {"p5_netedge", "p50_netedge", "p95_netedge", "mean_netedge", "prob_positive", "slippage_mean"} <= set(
            result.keys()
        )

    def test_p5_le_p50_le_p95(self):
        result = simulate_netedge_mc(
            _make_history(),
            1000.0,
            50.0,
            20.0,
            10.0,
            100,
            5000,
            0.2,
            0.1,
            0.05,
            n_scenarios=1000,
            seed=11,
        )
        assert result["p5_netedge"] <= result["p50_netedge"] <= result["p95_netedge"]

    def test_prob_positive_in_unit_interval(self):
        result = simulate_netedge_mc(
            _make_history(),
            1000.0,
            50.0,
            20.0,
            10.0,
            100,
            5000,
            0.2,
            0.1,
            0.05,
            n_scenarios=500,
            seed=12,
        )
        assert 0.0 <= result["prob_positive"] <= 1.0
