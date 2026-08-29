"""Tests for the Statistical Acceptance Gate (سند v5.0 §7.2).

Covers the four conditions:
1. OOS sample count ≥ 100
2. Wilson 95% lower CI on win rate > break-even (after costs)
3. Annualised Sharpe positive in both halves of the OOS window
4. MC slippage stability ≥ 90% (when MC samples provided)
"""

from __future__ import annotations

import pytest

from services.statistical_acceptance_gate import (
    AcceptanceDecision,
    TradeOutcome,
    annualised_sharpe,
    ev_stability,
    evaluate_acceptance,
    wilson_ci_lower,
)


class TestWilsonCI:
    def test_zero_samples_returns_zero(self):
        assert wilson_ci_lower(0.0, 0) == 0.0

    def test_known_50pct_100_samples(self):
        # 50/100 at 95% one-sided: lower bound around 0.42 (binom.test reference)
        lo = wilson_ci_lower(0.5, 100)
        assert 0.40 < lo < 0.45

    def test_higher_n_tightens_interval(self):
        lo_small = wilson_ci_lower(0.6, 50)
        lo_large = wilson_ci_lower(0.6, 500)
        assert lo_large > lo_small

    def test_proportion_one_returns_low(self):
        # 100% wins on small n → lower bound < 1.0 (rare events)
        lo = wilson_ci_lower(1.0, 30)
        assert 0.85 < lo < 1.0


class TestAnnualisedSharpe:
    def test_empty_returns_zero(self):
        assert annualised_sharpe([]) == 0.0

    def test_constant_returns_zero(self):
        # zero variance → defined as 0 to avoid /0 (any constant return)
        assert annualised_sharpe([0.5] * 50) == 0.0
        assert annualised_sharpe([-0.1] * 50) == 0.0
        assert annualised_sharpe([0.0] * 50) == 0.0

    def test_positive_sharpe_for_upward_returns(self):
        pnls = [0.01] * 252  # constant +1% per trade
        # zero variance → returns 0 by definition; replace with slight noise
        pnls = [0.01 + 0.001 * (i % 2) for i in range(252)]
        assert annualised_sharpe(pnls) > 0

    def test_negative_sharpe_for_downward_returns(self):
        pnls = [-0.01] * 252
        # constant negative → zero variance; add slight noise to make it measurable
        pnls = [-0.01 + 0.0005 * (i % 3) for i in range(252)]
        assert annualised_sharpe(pnls) < 0


class TestEVStability:
    def test_all_positive(self):
        assert ev_stability([0.1, 0.2, 0.05]) == 1.0

    def test_all_negative(self):
        assert ev_stability([-0.1, -0.2]) == 0.0

    def test_mixed(self):
        assert ev_stability([0.1, -0.1, 0.1, -0.1, 0.1]) == pytest.approx(0.6, abs=1e-9)

    def test_empty_returns_zero(self):
        assert ev_stability([]) == 0.0


def _good_trades(n: int = 120) -> list[TradeOutcome]:
    """OOS trades that should pass the gate: 60% wins, 1% cost, balanced halves."""
    return [TradeOutcome(pnl_pct=0.01 if i % 5 != 0 else -0.01, cost_pct=0.001, period_index=i % 2) for i in range(n)]


class TestEvaluateAcceptance:
    def test_passes_with_good_trades(self):
        decision = evaluate_acceptance(_good_trades(120), mc_ev_samples=[0.1] * 100)
        assert decision.passed, decision.failed_conditions
        assert decision.oos_samples == 120
        assert decision.win_rate > 0.5
        assert decision.sharpe_half_1 > 0
        assert decision.sharpe_half_2 > 0
        assert decision.ev_positive_in_scenarios == 1.0
        assert decision.failed_conditions == []

    def test_fails_on_too_few_samples(self):
        # 99 < 100 → fail condition #1
        decision = evaluate_acceptance(_good_trades(99), mc_ev_samples=[0.1] * 100)
        assert not decision.passed
        assert any("OOS samples" in f for f in decision.failed_conditions)

    def test_fails_on_breakeven_win_rate(self):
        # 50% wins, no clear positive edge → CI lower bound may still exceed
        # 0.50 with low n. Construct a noisier case: 50/100 wins with high
        # variance to push CI down.
        trades = [TradeOutcome(pnl_pct=0.5 if i % 2 == 0 else -0.5, cost_pct=0.01) for i in range(120)]
        decision = evaluate_acceptance(trades, mc_ev_samples=[0.1] * 100)
        # Net of cost, mean is ≈ 0 → win_rate ≈ 0.5; CI lower likely < 0.5
        assert decision.win_rate == pytest.approx(0.5, abs=1e-6)
        # The gate should fail condition #2 (CI ≤ break-even) OR #3 (Sharpe)
        assert not decision.passed

    def test_fails_on_negative_sharpe_half(self):
        # First half loses with noise, second half wins with noise → one Sharpe negative
        import random

        rng = random.Random(7)
        trades = []
        for i in range(120):
            base = -0.02 if i < 60 else 0.05
            noise = rng.uniform(-0.005, 0.005)
            trades.append(TradeOutcome(pnl_pct=base + noise, cost_pct=0.001, period_index=0 if i < 60 else 1))
        decision = evaluate_acceptance(trades, mc_ev_samples=[0.1] * 100)
        assert decision.sharpe_half_1 < 0
        assert not decision.passed
        assert any("Sharpe" in f for f in decision.failed_conditions)

    def test_fails_on_low_mc_stability(self):
        # Only 50% of MC scenarios have positive EV
        mc = [0.1] * 50 + [-0.1] * 50
        decision = evaluate_acceptance(_good_trades(120), mc_ev_samples=mc)
        assert decision.ev_positive_in_scenarios == pytest.approx(0.5, abs=1e-6)
        assert not decision.passed
        assert any("stability" in f for f in decision.failed_conditions)

    def test_mc_samples_optional(self):
        # When MC not provided, condition #4 is skipped (no penalty)
        decision = evaluate_acceptance(_good_trades(120))
        assert decision.passed

    def test_costs_reduce_win_rate(self):
        # Trades with 0% gross but 1% cost → all become net losses
        trades = [TradeOutcome(pnl_pct=0.0, cost_pct=0.01) for _ in range(120)]
        decision = evaluate_acceptance(trades, mc_ev_samples=[0.1] * 100)
        assert decision.win_rate == 0.0
        assert not decision.passed

    def test_empty_trades_fails(self):
        decision = evaluate_acceptance([], mc_ev_samples=[])
        assert not decision.passed
        assert any("OOS samples" in f for f in decision.failed_conditions)

    def test_two_halves_use_chronological_split(self):
        # With 100 trades, half=50; first 50 losers (with noise), last 50 winners
        import random

        rng = random.Random(11)
        trades = []
        for i in range(100):
            base = -0.01 if i < 50 else 0.05
            noise = rng.uniform(-0.005, 0.005)
            trades.append(TradeOutcome(pnl_pct=base + noise, cost_pct=0.001))
        decision = evaluate_acceptance(trades, mc_ev_samples=[0.1] * 100)
        # First half is net losing → sharpe_half_1 negative
        assert decision.sharpe_half_1 < 0
        assert not decision.passed

    def test_break_even_rate_override(self):
        # Set break-even above the realised win rate (~0.8) so the gate fails
        decision = evaluate_acceptance(_good_trades(120), mc_ev_samples=[0.1] * 100, break_even_rate=0.9)
        assert not decision.passed
        assert any("break-even" in f for f in decision.failed_conditions)

    def test_decision_dataclass_defaults(self):
        d = AcceptanceDecision(
            passed=True,
            oos_samples=10,
            win_rate=0.6,
            win_rate_ci_low=0.5,
            break_even_adjusted=0.5,
            sharpe_half_1=1.0,
            sharpe_half_2=0.5,
            ev_positive_in_scenarios=0.95,
        )
        assert d.failed_conditions == []
