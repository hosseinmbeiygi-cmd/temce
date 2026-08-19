"""Unit tests for the comprehensive backtesting framework.

Covers the pure-logic engines with synthetic data — no DB or network:
  - ``VectorizedBacktest`` (metrics + data-length guard)
  - ``WalkForwardEngine`` (rolling/expanding splits + evaluate)
  - ``CPCV`` (combinatorial purged splits with embargo)
  - ``MonteCarloEngine`` (shuffle_test + scenario_test)
  - ``StressTestEngine`` (TSE scenarios)
  - ``RegimeEvaluator`` (per-regime returns)
  - ``LiquidityAnalyzer`` (days-to-liquidate + risk)
  - ``StatisticalValidator`` (deflated sharpe + reality check)
"""

from __future__ import annotations

import pytest

from services.backtest_framework import (
    CPCV,
    LiquidityAnalyzer,
    MonteCarloEngine,
    RegimeEvaluator,
    StatisticalValidator,
    StressTestEngine,
    VectorizedBacktest,
    WalkForwardEngine,
)

# ── VectorizedBacktest ────────────────────────────────────────────────────


class TestVectorizedBacktest:
    def test_mismatched_lengths_return_error(self) -> None:
        result = VectorizedBacktest().run([100.0, 101.0], [1])
        assert "error" in result

    def test_computes_metrics_on_uptrend(self) -> None:
        # Constant buy signal on an up-trending series → positive return.
        prices = [100.0, 101.0, 102.0, 103.0, 104.0]
        result = VectorizedBacktest().run(prices, [1, 1, 1, 1, 1])

        assert result["method"] == "vectorized"
        assert result["total_return_pct"] > 0
        assert result["final_equity"] > 1_000_000_000
        assert result["max_drawdown_pct"] >= 0

    def test_bear_signal_loses_money(self) -> None:
        prices = [100.0, 99.0, 98.0, 97.0]
        result = VectorizedBacktest().run(prices, [1, 1, 1, 1])
        assert result["total_return_pct"] < 0

    def test_insufficient_data(self) -> None:
        result = VectorizedBacktest().run([100.0], [1])
        assert "error" in result


# ── WalkForwardEngine ─────────────────────────────────────────────────────


class TestWalkForwardEngine:
    def test_rolling_split_generates_windows(self) -> None:
        engine = WalkForwardEngine(windows=3, train_ratio=0.7, mode="rolling")
        data = list(range(60))
        pairs = engine.split(data)

        assert len(pairs) == 3
        for train, test in pairs:
            assert train and test
            assert not set(train) & set(test)  # no overlap

    def test_expanding_split_grows_train(self) -> None:
        engine = WalkForwardEngine(windows=3, mode="expanding")
        data = list(range(80))
        pairs = engine.split(data)

        assert len(pairs) == 3
        train_sizes = [len(t) for t, _ in pairs]
        assert train_sizes == sorted(train_sizes)  # expanding

    def test_evaluate_validates_good_strategy(self) -> None:
        def _good(train, **kw):
            return {"sharpe_ratio": 1.5, "total_return_pct": 10.0}

        result = WalkForwardEngine(windows=3).evaluate(_good, list(range(60)))

        assert result["validated"] is True
        assert result["avg_oos_sharpe"] > 0

    def test_evaluate_returns_not_validated_on_empty(self) -> None:
        def _fail(train, **kw):
            return {"error": "no data"}

        result = WalkForwardEngine(windows=3).evaluate(_fail, list(range(30)))
        assert result["validated"] is False


# ── CPCV ──────────────────────────────────────────────────────────────────


class TestCPCV:
    def test_generates_purged_combinations(self) -> None:
        cv = CPCV(n_groups=4, embargo_pct=0.01)
        splits = cv.generate_combinations(n_total=100)

        # C(4,2) = 6 test combinations.
        assert len(splits) == 6
        # Edge pair (first+last group) may purge the whole train set, so only
        # assert the invariant that *when* train survives it is disjoint from
        # the test window (embargo behaviour).
        surviving = [s for s in splits if s["train"]]
        assert surviving  # at least some splits keep training data
        for split in splits:
            assert split["test"]
            assert not set(split["train"]) & set(split["test"])


# ── MonteCarloEngine ──────────────────────────────────────────────────────


class TestMonteCarloEngine:
    def test_shuffle_test_returns_p_value(self) -> None:
        equity = [100.0, 101.0, 102.0, 101.5, 103.0, 104.0]
        result = MonteCarloEngine(n_simulations=50).shuffle_test(equity)

        assert "original_sharpe" in result
        assert 0.0 <= result["p_value"] <= 1.0
        assert result["simulations"] == 50

    def test_shuffle_test_empty_returns_error(self) -> None:
        result = MonteCarloEngine().shuffle_test([100.0])
        assert "error" in result

    def test_scenario_test_applies_costs(self) -> None:
        equity = [100.0, 101.0, 102.0, 103.0, 104.0]
        scenarios = [
            {"name": "base", "cost_multiplier": 1.0},
            {"name": "high-cost", "cost_multiplier": 2.0},
        ]
        results = MonteCarloEngine().scenario_test(equity, scenarios)

        assert len(results) == 2
        assert results[0]["scenario"] == "base"
        assert results[1]["scenario"] == "high-cost"
        assert "total_return_pct" in results[0]
        assert "sharpe" in results[0]


# ── StressTestEngine ──────────────────────────────────────────────────────


class TestStressTestEngine:
    def test_runs_all_tse_scenarios(self) -> None:
        equity = [100.0, 101.0, 100.5, 102.0, 103.0]
        results = StressTestEngine().run(equity, capital=1e9)

        assert len(results) == len(StressTestEngine.TSE_SCENARIOS)
        for r in results:
            assert "scenario" in r
            assert "survived" in r
            assert "final_equity" in r


# ── RegimeEvaluator ───────────────────────────────────────────────────────


class TestRegimeEvaluator:
    def test_splits_returns_per_regime(self) -> None:
        equity = [100.0, 102.0, 104.0, 99.0, 98.0, 101.0, 103.0]
        # 0 = نزولی, 1 = نوسانی, 2 = صعودی
        labels = [2, 2, 0, 0, 1, 1]
        result = RegimeEvaluator().evaluate(equity, labels)

        assert "صعودی" in result
        assert "نزولی" in result
        assert result["صعودی"]["days"] >= 1
        assert "sharpe" in result["صعودی"]

    def test_insufficient_regime_labels(self) -> None:
        result = RegimeEvaluator().evaluate([100.0], [])
        assert result == {}


# ── LiquidityAnalyzer ─────────────────────────────────────────────────────


class TestLiquidityAnalyzer:
    def test_computes_days_to_liquidate(self) -> None:
        equity = [100.0, 101.0, 102.0]
        positions = [100_000.0, 200_000.0, 50_000.0]
        volumes = [1_000_000.0, 1_000_000.0, 1_000_000.0]
        result = LiquidityAnalyzer().analyze(equity, positions, volumes, participation_rate=0.1)

        # executable = 100k per day → dtl = pv / 100k
        assert result["avg_days_to_liquidate"] == pytest.approx(
            (1.0 + 2.0 + 0.5) / 3, abs=0.1
        )
        # avg_dtl ≈ 1.17 → LOW risk (deterministic for this input).
        assert result["liquidity_risk"] == "LOW"

    def test_empty_returns_zero_risk(self) -> None:
        result = LiquidityAnalyzer().analyze([], [], [])
        assert result["avg_days_to_liquidate"] == 0.0
        assert result["max_days_to_liquidate"] == 0.0


# ── StatisticalValidator ──────────────────────────────────────────────────


class TestStatisticalValidator:
    def test_deflated_sharpe_high_value_is_significant(self) -> None:
        result = StatisticalValidator().deflated_sharpe(
            observed_sharpe=3.0, n_trials=50, n_observations=500
        )

        assert result["observed_sharpe"] == 3.0
        assert "deflated_sharpe" in result
        assert result["significant"] is True

    def test_deflated_sharpe_low_value_not_significant(self) -> None:
        result = StatisticalValidator().deflated_sharpe(
            observed_sharpe=0.1, n_trials=1000, n_observations=100
        )

        assert result["significant"] is False

    def test_reality_check_insufficient_data(self) -> None:
        result = StatisticalValidator().reality_check([], [])
        assert "error" in result

    def test_reality_check_best_strategy_wins(self) -> None:
        benchmark = [0.0, 0.0, 0.0, 0.0]
        good = [0.01, 0.02, 0.01, 0.02]
        bad = [-0.01, -0.02, -0.01, -0.02]
        result = StatisticalValidator().reality_check([good, bad], benchmark)

        assert result["n_strategies_tested"] == 2
        assert result["best_excess_performance"] > 0
