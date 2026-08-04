"""Unit tests for SignalDecisionEngine — 10-gate pipeline, grading, and market-aware config.

Tests cover:
  - Individual gate PASS/WARN/BLOCK conditions for each of 10 gates
  - Full evaluate() flow (RELEASE / WATCHLIST / REJECT verdicts)
  - signal_grade() logic (A+ / A / B / WATCHLIST / REJECT)
  - Market-specific config overrides via get_gate_config()
  - SignalPolicy deep-merge & copy isolation
  - Edge cases (zero values, rule-based signals, extreme volatility)
"""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path

import pytest

from services.signal_decision_engine import (
    Decision,
    FinalVerdict,
    GateResult,
    GateVerdict,
    SignalCandidate,
    SignalDecisionEngine,
    SignalPolicy,
)

# ═══════════════════════════════════════════════════════════════════════════════
# ── Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_candidate(overrides: dict | None = None) -> SignalCandidate:
    """Create a default "perfect pass" candidate that should RELEASE with A grade.

    raw_score=0.85 gives trend_strength = |0.85-0.5|*2 = 0.70 > 0.60 → TREND regime,
    which passes the regime gate (TREND is NOT in blocked_regimes).
    """
    base: dict = {
        "signal_id": "test_001",
        "symbol": "فولاد",
        "name": "فولاد مبارکه",
        "market": "stock",
        "direction": "buy",
        "timeframe": "daily",
        "raw_score": 0.85,  # strong trend so regime gate doesn't block
        "ml_score": 0.0,
        "calibrated_probability": 0.72,
        "boosted_score": 80.0,
        "active_models": 0,
        "agreeing_models": 0,
        "model_disagreement": 0.0,
        "data_quality_score": 0.95,
        "missing_data_count": 0,
        "liquidity_score": 0.8,
        "fill_probability": 0.8,
        "risk_reward": 2.0,
        "stop_loss_pct": 0.05,
        "target_pct": 0.10,
        "volatility_regime": 0.4,
        "open_risk_pct": 0.05,
        "correlated_exposure_pct": 0.10,
        "portfolio_risk_approved": True,
        "feature_drift": 0.05,
        "prediction_drift": 0.0,
        "price": 50000,
        "signal_type": "rule",
        "best_class_probability": 0.72,
        "second_class_probability": 0.12,
    }
    if overrides:
        base.update(overrides)
    return SignalCandidate(**base)


def _make_engine() -> SignalDecisionEngine:
    """Create a SignalDecisionEngine with default policy (no YAML file)."""
    return SignalDecisionEngine()


def _make_decision(
    verdict: FinalVerdict = FinalVerdict.RELEASE,
    prob: float = 0.72,
    rr: float = 2.0,
    net_exp: float = 0.15,
    market: str = "stock",
    gate_results: list[GateResult] | None = None,
) -> Decision:
    """Create a Decision for grading tests."""
    if gate_results is None:
        gate_results = []
    return Decision(
        signal_id="test_001",
        symbol="فولاد",
        market=market,
        direction="buy",
        verdict=verdict,
        calibrated_probability=prob,
        effective_threshold=0.58,
        gate_results=gate_results,
        net_expectancy_r=net_exp,
        risk_reward_ratio=rr,
        fill_probability=0.8,
        evaluated_at="2026-01-01T00:00:00",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ── SignalPolicy Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSignalPolicy:
    def test_default_version_and_name(self):
        policy = SignalPolicy()
        assert policy.version == "1.0.0"
        assert policy.name == "default_conservative"

    def test_global_defaults_structure(self):
        policy = SignalPolicy()
        assert policy.get_gate_config("data", "")["min_data_quality"] == 0.80
        assert policy.get_gate_config("probability", "")["base_threshold"] == 0.55
        assert policy.get_gate_config("liquidity", "")["minimum_score"] == 0.50
        assert policy.get_gate_config("expectancy", "")["minimum_net_expectancy_r"] == 0.05

    def test_get_gate_config_unknown_market_returns_globals(self):
        policy = SignalPolicy()
        cfg = policy.get_gate_config("data", "nonexistent_market")
        assert cfg["min_data_quality"] == 0.80

    def test_get_gate_config_unknown_gate_returns_empty(self):
        policy = SignalPolicy()
        cfg = policy.get_gate_config("nonexistent_gate", "")
        assert cfg == {}

    def test_get_gate_config_with_market_overrides(self):
        """Verify that market-specific overrides are applied via deep-merge."""
        policy = SignalPolicy()
        # Manually inject a market override to simulate YAML loading
        policy._policy_data["crypto"] = {
            "probability": {"base_threshold": 0.60},
            "data": {"min_data_quality": 0.90},
        }

        crypto_prob = policy.get_gate_config("probability", "crypto")
        assert crypto_prob["base_threshold"] == 0.60
        # Non-overridden fields should still come from globals
        assert crypto_prob["volatility_penalty"] == 0.05

        crypto_data = policy.get_gate_config("data", "crypto")
        assert crypto_data["min_data_quality"] == 0.90
        assert crypto_data["max_missing_fields"] == 3  # global default, not overridden

    def test_get_gate_config_no_mutation_leak(self):
        """Verify that market-specific overrides don't mutate global defaults."""
        policy = SignalPolicy()
        policy._policy_data["stock"] = {
            "probability": {"base_threshold": 0.58},
        }

        # First call with market override
        stock_cfg = policy.get_gate_config("probability", "stock")
        assert stock_cfg["base_threshold"] == 0.58

        # Second call without market (global) — should still be 0.55
        global_cfg = policy.get_gate_config("probability", "")
        assert global_cfg["base_threshold"] == 0.55

        # Also test different market
        crypto_cfg = policy.get_gate_config("probability", "crypto")
        assert crypto_cfg["base_threshold"] == 0.55  # crypto has no override → global

    def test_get_gate_config_multiple_markets_independent(self):
        """Verify that two market calls don't interfere with each other."""
        policy = SignalPolicy()
        policy._policy_data["stock"] = {
            "probability": {"base_threshold": 0.58, "volatility_penalty": 0.06},
        }
        policy._policy_data["crypto"] = {
            "probability": {"base_threshold": 0.60, "volatility_penalty": 0.08},
        }

        stock = policy.get_gate_config("probability", "stock")
        crypto = policy.get_gate_config("probability", "crypto")

        assert stock["base_threshold"] == 0.58
        assert crypto["base_threshold"] == 0.60
        assert stock["volatility_penalty"] == 0.06
        assert crypto["volatility_penalty"] == 0.08
        # Global unchanged
        global_cfg = policy.get_gate_config("probability", "")
        assert global_cfg["base_threshold"] == 0.55

    def test_effective_threshold_default(self):
        policy = SignalPolicy()
        t = policy.get_effective_threshold(volatility=0.5, liquidity=0.7, drift=0.0)
        assert t == 0.55  # no penalties applied

    def test_effective_threshold_with_penalties(self):
        policy = SignalPolicy()
        # High volatility + low liquidity + high drift
        # base=0.55 + vol_penalty=0.05 + liq_penalty=0.03 + drift_penalty=0.04 = 0.67
        t = policy.get_effective_threshold(volatility=0.8, liquidity=0.3, drift=0.5)
        assert t == pytest.approx(0.67)

    def test_effective_threshold_capped_at_80(self):
        policy = SignalPolicy()
        # Extreme penalties
        policy._policy_data["probability"]["volatility_penalty"] = 0.20
        policy._policy_data["probability"]["liquidity_penalty"] = 0.20
        policy._policy_data["probability"]["drift_penalty"] = 0.20
        t = policy.get_effective_threshold(volatility=0.9, liquidity=0.1, drift=0.9)
        assert t == 0.80  # capped

    def test_effective_threshold_with_market(self):
        """Market-specific probability config changes the effective threshold."""
        policy = SignalPolicy()
        policy._policy_data["crypto"] = {
            "probability": {"base_threshold": 0.60, "volatility_penalty": 0.08},
        }

        # Without market: base=0.55 + vol_penalty=0.05 = 0.60
        t_global = policy.get_effective_threshold(volatility=0.8, liquidity=0.7, drift=0.0, market="")
        assert t_global == pytest.approx(0.60)

        # With crypto market: base=0.60 + vol_penalty=0.08 = 0.68
        t_crypto = policy.get_effective_threshold(volatility=0.8, liquidity=0.7, drift=0.0, market="crypto")
        assert t_crypto == pytest.approx(0.68)

    def test_get_grades_config(self):
        policy = SignalPolicy()
        grades = policy.get_grades_config("")
        assert grades["a_plus"]["min_probability"] == 0.70
        assert grades["a"]["min_rr"] == 1.5

    def test_get_grades_config_market_override(self):
        policy = SignalPolicy()
        policy._policy_data["crypto"] = {
            "grades": {"a_plus": {"min_probability": 0.75}},
        }
        grades = policy.get_grades_config("crypto")
        assert grades["a_plus"]["min_probability"] == 0.75
        # Non-overridden fields preserved
        assert grades["a_plus"]["min_rr"] == 2.0

    def test_yaml_loading(self):
        """Test loading a policy from a temporary YAML file."""
        yaml_content = """
policy_version: "2.0.0"
policy_name: "test_policy"
stock:
  probability:
    base_threshold: 0.60
        """
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            policy = SignalPolicy(json_path=tmp_path)
            assert policy.version == "2.0.0"
            assert policy.name == "test_policy"
            stock_prob = policy.get_gate_config("probability", "stock")
            assert stock_prob["base_threshold"] == 0.60
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_yaml_none_content(self):
        """Empty YAML file should not break loading."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write("")
            tmp_path = f.name

        try:
            policy = SignalPolicy(json_path=tmp_path)
            assert policy.version == "1.0.0"  # default
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_deep_merge_nested(self):
        base = {"a": {"b": 1, "c": 2}, "d": 3}
        override = {"a": {"b": 99}, "e": 4}
        merged = copy.deepcopy(base)
        SignalPolicy._deep_merge(merged, override)
        assert merged["a"]["b"] == 99  # overridden
        assert merged["a"]["c"] == 2  # preserved
        assert merged["d"] == 3  # preserved
        assert merged["e"] == 4  # added


# ═══════════════════════════════════════════════════════════════════════════════
# ── Individual Gate Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestGateDataQuality:
    @pytest.mark.asyncio
    async def test_pass(self):
        engine = _make_engine()
        candidate = _make_candidate({"data_quality_score": 0.95, "missing_data_count": 0})
        result = await engine._gate_data_quality(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_block_low_quality(self):
        engine = _make_engine()
        candidate = _make_candidate({"data_quality_score": 0.50, "missing_data_count": 0})
        result = await engine._gate_data_quality(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_warn_missing_fields(self):
        engine = _make_engine()
        candidate = _make_candidate({"data_quality_score": 0.85, "missing_data_count": 5})
        result = await engine._gate_data_quality(candidate, "stock")
        assert result.verdict == GateVerdict.WARN


class TestGateModel:
    @pytest.mark.asyncio
    async def test_rule_signal_always_passes(self):
        engine = _make_engine()
        candidate = _make_candidate({"signal_type": "rule", "active_models": 0, "agreeing_models": 0, "model_disagreement": 0.0, "ml_score": 0.0})
        result = await engine._gate_model(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_hybrid_block_no_models(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "signal_type": "hybrid",
                "active_models": 0,
                "ml_score": 0.6,
            }
        )
        result = await engine._gate_model(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_hybrid_warn_disagreement(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "signal_type": "hybrid",
                "active_models": 3,
                "agreeing_models": 1,
                "model_disagreement": 0.8,
                "ml_score": 0.6,
            }
        )
        result = await engine._gate_model(candidate, "stock")
        assert result.verdict == GateVerdict.WARN

    @pytest.mark.asyncio
    async def test_hybrid_pass(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "signal_type": "hybrid",
                "active_models": 3,
                "agreeing_models": 3,
                "model_disagreement": 0.1,
                "ml_score": 0.7,
            }
        )
        result = await engine._gate_model(candidate, "stock")
        assert result.verdict == GateVerdict.PASS


class TestGateProbability:
    @pytest.mark.asyncio
    async def test_pass(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "calibrated_probability": 0.72,
                "best_class_probability": 0.72,
                "second_class_probability": 0.12,
            }
        )
        result = await engine._gate_probability(candidate, 0.58, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_block_below_threshold(self):
        engine = _make_engine()
        candidate = _make_candidate({"calibrated_probability": 0.50})
        result = await engine._gate_probability(candidate, 0.58, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_warn_small_margin(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "calibrated_probability": 0.65,
                "best_class_probability": 0.65,
                "second_class_probability": 0.60,  # margin = 0.05 < 0.10
            }
        )
        result = await engine._gate_probability(candidate, 0.58, "stock")
        assert result.verdict == GateVerdict.WARN


class TestGateRegime:
    @pytest.mark.asyncio
    async def test_pass_trend(self):
        engine = _make_engine()
        candidate = _make_candidate({"volatility_regime": 0.4, "raw_score": 0.85})
        result = await engine._gate_regime(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_block_crisis(self):
        engine = _make_engine()
        candidate = _make_candidate({"volatility_regime": 0.9, "raw_score": 0.5})
        result = await engine._gate_regime(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_warn_high_volatility(self):
        engine = _make_engine()
        candidate = _make_candidate({"volatility_regime": 0.7, "raw_score": 0.5})
        result = await engine._gate_regime(candidate, "stock")
        assert result.verdict == GateVerdict.WARN

    @pytest.mark.asyncio
    async def test_pass_unknown_not_blocked(self):
        """UNKNOWN regime is NOT in blocked_regimes by default, so signals pass."""
        engine = _make_engine()
        candidate = _make_candidate({"volatility_regime": 0.5, "raw_score": 0.5})
        result = await engine._gate_regime(candidate, "stock")
        assert result.verdict == GateVerdict.PASS


class TestGateConsensus:
    @pytest.mark.asyncio
    async def test_rule_always_passes(self):
        engine = _make_engine()
        candidate = _make_candidate({"signal_type": "rule", "active_models": 0, "agreeing_models": 0})
        result = await engine._gate_consensus(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_hybrid_block_no_models(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "signal_type": "hybrid",
                "active_models": 0,
                "agreeing_models": 0,
            }
        )
        result = await engine._gate_consensus(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_hybrid_block_no_agreement(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "signal_type": "hybrid",
                "active_models": 3,
                "agreeing_models": 0,
            }
        )
        result = await engine._gate_consensus(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_hybrid_pass_full_agreement(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "signal_type": "hybrid",
                "active_models": 3,
                "agreeing_models": 3,
            }
        )
        result = await engine._gate_consensus(candidate, "stock")
        assert result.verdict == GateVerdict.PASS


class TestGateLiquidity:
    @pytest.mark.asyncio
    async def test_pass(self):
        engine = _make_engine()
        candidate = _make_candidate({"liquidity_score": 0.8, "fill_probability": 0.8})
        result = await engine._gate_liquidity(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_block_low_score(self):
        engine = _make_engine()
        candidate = _make_candidate({"liquidity_score": 0.3, "fill_probability": 0.5})
        result = await engine._gate_liquidity(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_warn_low_fill(self):
        engine = _make_engine()
        candidate = _make_candidate({"liquidity_score": 0.7, "fill_probability": 0.3})
        result = await engine._gate_liquidity(candidate, "stock")
        assert result.verdict == GateVerdict.WARN


class TestGateRiskReward:
    @pytest.mark.asyncio
    async def test_pass(self):
        engine = _make_engine()
        candidate = _make_candidate({"risk_reward": 2.0})
        result = await engine._gate_risk_reward(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_block_below_watchlist(self):
        engine = _make_engine()
        candidate = _make_candidate({"risk_reward": 0.3})
        result = await engine._gate_risk_reward(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_warn_below_trade(self):
        engine = _make_engine()
        candidate = _make_candidate({"risk_reward": 0.7})
        result = await engine._gate_risk_reward(candidate, "stock")
        assert result.verdict == GateVerdict.WARN

    @pytest.mark.asyncio
    async def test_zero_rr_blocks(self):
        engine = _make_engine()
        candidate = _make_candidate({"risk_reward": 0.0})
        result = await engine._gate_risk_reward(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK


class TestGateExpectancy:
    @pytest.mark.asyncio
    async def test_pass(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "calibrated_probability": 0.72,
                "risk_reward": 2.0,
                "stop_loss_pct": 0.05,
            }
        )
        result = await engine._gate_expectancy(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_block_negative_expectancy(self):
        """Win rate 40%, RR 0.5 → gross = 0.4*0.5 - 0.6*1.0 = -0.4 → BLOCK."""
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "calibrated_probability": 0.40,
                "risk_reward": 0.5,
                "stop_loss_pct": 0.05,
            }
        )
        result = await engine._gate_expectancy(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_warn_low_positive_expectancy(self):
        """Win rate 55%, RR 1.0, SL 5%:
        gross = 0.55*1.0 - 0.45*1.0 = 0.10
        cost = 0.003/0.05 = 0.06
        net = 0.04  →  0 <= 0.04 < 0.05 → WARN."""
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "calibrated_probability": 0.55,
                "risk_reward": 1.0,
                "stop_loss_pct": 0.05,
            }
        )
        result = await engine._gate_expectancy(candidate, "stock")
        assert result.verdict == GateVerdict.WARN


class TestGatePortfolio:
    @pytest.mark.asyncio
    async def test_pass(self):
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "open_risk_pct": 0.05,
                "correlated_exposure_pct": 0.10,
                "portfolio_risk_approved": True,
            }
        )
        result = await engine._gate_portfolio(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_block_not_approved(self):
        engine = _make_engine()
        candidate = _make_candidate({"portfolio_risk_approved": False})
        result = await engine._gate_portfolio(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_block_excess_open_risk(self):
        engine = _make_engine()
        candidate = _make_candidate({"open_risk_pct": 0.30})
        result = await engine._gate_portfolio(candidate, "stock")
        assert result.verdict == GateVerdict.BLOCK

    @pytest.mark.asyncio
    async def test_warn_excess_correlated(self):
        engine = _make_engine()
        candidate = _make_candidate({"correlated_exposure_pct": 0.50})
        result = await engine._gate_portfolio(candidate, "stock")
        assert result.verdict == GateVerdict.WARN


class TestGateExecution:
    @pytest.mark.asyncio
    async def test_pass(self):
        engine = _make_engine()
        candidate = _make_candidate({"spread_pct": 0.001, "price": 50000})
        result = await engine._gate_execution(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_pass_default_min_spread_is_zero(self):
        """With min_spread_pct=0.0 (default), spread is never checked."""
        engine = _make_engine()
        candidate = _make_candidate({"spread_pct": 0.1, "price": 50000})
        result = await engine._gate_execution(candidate, "stock")
        assert result.verdict == GateVerdict.PASS

    @pytest.mark.asyncio
    async def test_warn_high_spread_when_configured(self):
        """When min_spread_pct > 0, spread above it triggers WARN."""
        engine = _make_engine()
        # Override the execution config
        engine._policy._policy_data["execution"]["min_spread_pct"] = 0.02
        candidate = _make_candidate({"spread_pct": 0.05, "price": 50000})
        result = await engine._gate_execution(candidate, "stock")
        assert result.verdict == GateVerdict.WARN


# ═══════════════════════════════════════════════════════════════════════════════
# ── Full evaluate() Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluate:
    @pytest.mark.asyncio
    async def test_perfect_candidate_releases(self):
        """A perfect candidate (all gates pass) should get RELEASE."""
        engine = _make_engine()
        candidate = _make_candidate()
        decision = await engine.evaluate(candidate)
        assert decision.verdict == FinalVerdict.RELEASE
        assert decision.is_releasable()
        assert len(decision.gate_results) == 10

    @pytest.mark.asyncio
    async def test_bad_data_quality_rejects(self):
        """Low data quality should produce a BLOCK on data_quality gate → REJECT."""
        engine = _make_engine()
        candidate = _make_candidate({"data_quality_score": 0.3})
        decision = await engine.evaluate(candidate)
        assert decision.verdict == FinalVerdict.REJECT
        assert "data_quality" in decision.blocked_gates()

    @pytest.mark.asyncio
    async def test_low_probability_rejects(self):
        """Low calibrated probability should produce BLOCK on probability gate → REJECT."""
        engine = _make_engine()
        candidate = _make_candidate({"calibrated_probability": 0.45})
        decision = await engine.evaluate(candidate)
        assert decision.verdict == FinalVerdict.REJECT
        assert "probability" in decision.blocked_gates()

    @pytest.mark.asyncio
    async def test_multiple_warnings_watchlists(self):
        """Multiple WARN gates should produce WATCHLIST when > 2 warnings.

        raw_score=0.85 ensures trend_strength=0.70 > 0.60 → TREND regime,
        so the regime gate does NOT block."""
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "raw_score": 0.85,  # ensure strong trend → TREND regime
                "calibrated_probability": 0.68,
                "best_class_probability": 0.68,
                "second_class_probability": 0.63,  # margin 0.05 → WARN
                "risk_reward": 0.7,  # below min_trade → WARN
                "correlated_exposure_pct": 0.50,  # > 0.40 → WARN
            }
        )
        decision = await engine.evaluate(candidate)
        assert decision.verdict == FinalVerdict.WATCHLIST
        assert decision.warning_count() == 3

    @pytest.mark.asyncio
    async def test_risk_reward_zero_and_low_liquidity_blocks(self):
        """RR=0 → BLOCK on risk_reward, low liquidity → BLOCK → REJECT."""
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "risk_reward": 0.0,
                "liquidity_score": 0.3,
            }
        )
        decision = await engine.evaluate(candidate)
        assert decision.verdict == FinalVerdict.REJECT
        assert len(decision.blocked_gates()) >= 2

    @pytest.mark.asyncio
    async def test_decision_includes_net_expectancy(self):
        engine = _make_engine()
        candidate = _make_candidate()
        decision = await engine.evaluate(candidate)
        assert decision.net_expectancy_r != 0.0
        assert decision.risk_reward_ratio == 2.0
        assert decision.fill_probability == 0.8
        assert len(decision.evaluated_at) > 0

    @pytest.mark.asyncio
    async def test_market_affects_threshold(self):
        """Crypto signals get a higher effective threshold than stock."""
        engine = _make_engine()
        # Inject crypto market overrides
        engine._policy._policy_data["crypto"] = {
            "probability": {"base_threshold": 0.60, "volatility_penalty": 0.08},
        }
        # Same candidate, different markets
        stock_candidate = _make_candidate({"market": "stock", "volatility_regime": 0.8})
        crypto_candidate = _make_candidate({"market": "crypto", "volatility_regime": 0.8})

        stock_decision = await engine.evaluate(stock_candidate)
        crypto_decision = await engine.evaluate(crypto_candidate)

        assert crypto_decision.effective_threshold > stock_decision.effective_threshold


# ═══════════════════════════════════════════════════════════════════════════════
# ── Grading Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSignalGrade:
    def test_a_plus(self):
        engine = _make_engine()
        decision = _make_decision(prob=0.72, rr=2.0, net_exp=0.25)
        grade = engine.signal_grade(decision)
        assert grade == "A+"

    def test_a_plus_requires_all_gates_pass(self):
        """A+ requires all_pass_required=True by default — blocked gate prevents it."""
        engine = _make_engine()
        blocked = [
            GateResult(
                gate_name="liquidity",
                verdict=GateVerdict.BLOCK,
                score=0.3,
                reason="test",
            )
        ]
        decision = _make_decision(prob=0.72, rr=2.0, net_exp=0.25, gate_results=blocked)
        grade = engine.signal_grade(decision)
        assert grade != "A+"
        # Should fall to A (if prob/rr/exp meet A thresholds but warning count <= 1)
        assert grade == "A"

    def test_a_grade(self):
        engine = _make_engine()
        decision = _make_decision(prob=0.67, rr=1.6, net_exp=0.14)
        grade = engine.signal_grade(decision)
        assert grade == "A"

    def test_a_grade_with_one_warning(self):
        """A allows up to 1 warning."""
        engine = _make_engine()
        warned = [
            GateResult(
                gate_name="liquidity",
                verdict=GateVerdict.WARN,
                score=0.5,
                reason="test",
            )
        ]
        decision = _make_decision(prob=0.67, rr=1.6, net_exp=0.14, gate_results=warned)
        grade = engine.signal_grade(decision)
        assert grade == "A"

    def test_a_grade_with_two_warnings_downgrades(self):
        """A allows max 1 warning, 2 warnings → B or lower."""
        engine = _make_engine()
        warned = [
            GateResult(
                gate_name="liquidity",
                verdict=GateVerdict.WARN,
                score=0.5,
                reason="test",
            ),
            GateResult(
                gate_name="execution",
                verdict=GateVerdict.WARN,
                score=0.5,
                reason="test",
            ),
        ]
        decision = _make_decision(prob=0.67, rr=1.6, net_exp=0.14, gate_results=warned)
        grade = engine.signal_grade(decision)
        assert grade == "B"  # falls to B (allows up to 2 warnings)

    def test_b_grade(self):
        engine = _make_engine()
        decision = _make_decision(prob=0.62, rr=1.1, net_exp=0.06)
        grade = engine.signal_grade(decision)
        assert grade == "B"

    def test_b_grade_with_two_warnings(self):
        """B allows up to 2 warnings."""
        engine = _make_engine()
        warned = [
            GateResult(
                gate_name="liquidity",
                verdict=GateVerdict.WARN,
                score=0.5,
                reason="test",
            ),
            GateResult(
                gate_name="risk_reward",
                verdict=GateVerdict.WARN,
                score=0.6,
                reason="test",
            ),
        ]
        decision = _make_decision(prob=0.62, rr=1.1, net_exp=0.06, gate_results=warned)
        grade = engine.signal_grade(decision)
        assert grade == "B"

    def test_watchlist_grade(self):
        """WATCHLIST verdict with 55% prob → WATCHLIST grade."""
        engine = _make_engine()
        decision = _make_decision(verdict=FinalVerdict.WATCHLIST, prob=0.55, rr=0.0, net_exp=0.0)
        grade = engine.signal_grade(decision)
        assert grade == "WATCHLIST"

    def test_reject_grade(self):
        """REJECT verdict → REJECT grade."""
        engine = _make_engine()
        decision = _make_decision(verdict=FinalVerdict.REJECT, prob=0.45, rr=0.3, net_exp=-0.1)
        grade = engine.signal_grade(decision)
        assert grade == "REJECT"

    def test_market_specific_grades_crypto(self):
        """Crypto has higher A+ bar (0.75 vs 0.70) — 0.72 prob should get A not A+."""
        engine = _make_engine()
        engine._policy._policy_data["crypto"] = {
            "grades": {
                "a_plus": {
                    "min_probability": 0.75,
                    "min_rr": 2.5,
                    "min_expectancy": 0.25,
                    "all_pass_required": True,
                }
            },
        }
        decision = _make_decision(prob=0.72, rr=2.0, net_exp=0.20, market="crypto")
        grade = engine.signal_grade(decision)
        assert grade != "A+"  # doesn't meet crypto's higher A+ bar
        # 0.72 >= 0.68 crypto A threshold... but A for crypto in YAML has 0.68 min_prob
        # With default globals: A min_prob=0.65, min_rr=1.5 — 0.72 >= 0.65, 2.0 >= 1.5 → A
        assert "A" in grade

    def test_market_specific_grades_stock_lower(self):
        """Stock has slightly higher A+ bar (0.72) — 0.71 should get A."""
        engine = _make_engine()
        engine._policy._policy_data["stock"] = {
            "grades": {
                "a_plus": {
                    "min_probability": 0.72,
                    "min_rr": 2.2,
                    "min_expectancy": 0.22,
                    "all_pass_required": True,
                }
            },
        }
        decision = _make_decision(prob=0.71, rr=2.0, net_exp=0.20, market="stock")
        grade = engine.signal_grade(decision)
        assert grade != "A+"
        assert grade == "A"


# ═══════════════════════════════════════════════════════════════════════════════
# ── Edge Cases & Helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeNetExpectancy:
    def test_positive_expectancy(self):
        """Win rate 70%, RR 2.0, SL 5% → gross = 0.7*2.0 - 0.3*1.0 = 1.1. cost = 0.003/0.05 = 0.06. net = 1.04"""
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "calibrated_probability": 0.70,
                "risk_reward": 2.0,
                "stop_loss_pct": 0.05,
            }
        )
        net = engine._compute_net_expectancy(candidate, "stock")
        assert net > 0.5
        assert net < 1.5

    def test_negative_expectancy(self):
        """Win rate 30%, RR 1.0, SL 5% → gross = 0.3*1.0 - 0.7*1.0 = -0.4. net ≈ -0.46"""
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "calibrated_probability": 0.30,
                "risk_reward": 1.0,
                "stop_loss_pct": 0.05,
            }
        )
        net = engine._compute_net_expectancy(candidate, "stock")
        assert net < 0

    def test_zero_stop_loss_uses_default_cost(self):
        """When stop_loss_pct = 0, cost_r = costs_pct directly (not divided by zero)."""
        engine = _make_engine()
        candidate = _make_candidate(
            {
                "calibrated_probability": 0.60,
                "risk_reward": 1.5,
                "stop_loss_pct": 0.0,
            }
        )
        net = engine._compute_net_expectancy(candidate, "stock")
        # Should not crash. net should be > -1
        assert net > -1

    def test_market_specific_costs(self):
        """Crypto has lower costs (0.1% vs 0.3%) so expectancy should be higher."""
        engine = _make_engine()
        engine._policy._policy_data["crypto"] = {
            "expectancy": {"costs_pct": 0.001},
        }
        candidate = _make_candidate(
            {
                "calibrated_probability": 0.60,
                "risk_reward": 1.5,
                "stop_loss_pct": 0.05,
            }
        )
        crypto_net = engine._compute_net_expectancy(candidate, "crypto")
        stock_net = engine._compute_net_expectancy(candidate, "stock")
        assert crypto_net > stock_net


class TestDetectRegime:
    @pytest.mark.asyncio
    async def test_crisis(self):
        engine = _make_engine()
        candidate = _make_candidate({"volatility_regime": 0.9, "raw_score": 0.5})
        assert await engine._detect_regime(candidate) == "CRISIS"

    @pytest.mark.asyncio
    async def test_high_volatility(self):
        engine = _make_engine()
        candidate = _make_candidate({"volatility_regime": 0.7, "raw_score": 0.5})
        assert await engine._detect_regime(candidate) == "HIGH_VOLATILITY"

    @pytest.mark.asyncio
    async def test_trend(self):
        engine = _make_engine()
        candidate = _make_candidate({"volatility_regime": 0.4, "raw_score": 0.85})
        assert await engine._detect_regime(candidate) == "TREND"

    @pytest.mark.asyncio
    async def test_range(self):
        engine = _make_engine()
        candidate = _make_candidate({"volatility_regime": 0.3, "raw_score": 0.52})
        assert await engine._detect_regime(candidate) == "RANGE"

    @pytest.mark.asyncio
    async def test_unknown(self):
        engine = _make_engine()
        # raw_score=0.65 → trend_strength = |0.65-0.5|*2 = 0.30
        # 0.30 is NOT > 0.60 and NOT < 0.30 → UNKNOWN
        candidate = _make_candidate({"volatility_regime": 0.5, "raw_score": 0.65})
        assert await engine._detect_regime(candidate) == "UNKNOWN"


class TestDecisionDataclass:
    def test_defaults(self):
        decision = _make_decision()
        assert decision.is_releasable()
        assert not decision.is_watchlisted()
        assert decision.all_gates_pass()
        assert decision.warning_count() == 0
        assert decision.blocked_gates() == []

    def test_to_dict(self):
        decision = _make_decision()
        d = decision.to_dict()
        assert d["verdict"] == "release"
        assert d["calibrated_probability"] == 0.72
        assert d["risk_reward_ratio"] == 2.0

    def test_blocked_gates_lists_names(self):
        blocked = [
            GateResult(gate_name="data_quality", verdict=GateVerdict.BLOCK, score=0.3),
            GateResult(gate_name="probability", verdict=GateVerdict.BLOCK, score=0.4),
        ]
        decision = _make_decision(verdict=FinalVerdict.REJECT, gate_results=blocked)
        assert decision.blocked_gates() == ["data_quality", "probability"]
        assert not decision.is_releasable()

    def test_warning_count(self):
        warned = [
            GateResult(gate_name="liquidity", verdict=GateVerdict.WARN, score=0.5),
            GateResult(gate_name="risk_reward", verdict=GateVerdict.WARN, score=0.6),
        ]
        decision = _make_decision(gate_results=warned)
        assert decision.warning_count() == 2


class TestGateResult:
    def test_to_dict(self):
        result = GateResult(
            gate_name="test_gate",
            verdict=GateVerdict.WARN,
            score=0.65,
            reason="test reason",
            details={"key": "value"},
        )
        d = result.to_dict()
        assert d["gate"] == "test_gate"
        assert d["verdict"] == "warn"
        assert d["score"] == 0.65
        assert d["reason"] == "test reason"
        assert d["details"] == {"key": "value"}
