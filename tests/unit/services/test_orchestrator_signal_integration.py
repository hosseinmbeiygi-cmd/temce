"""Unit tests for the orchestrator's signal integration methods.

Tests cover:
  - _apply_signal_decision(): full EnrichedSignal → SignalCandidate mapping
  - Decision verdict/grade storage on EnrichedSignal
  - Rejected vs released signal split
  - Graceful degradation when decision engine fails
  - Empty signal list edge case
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.quant_signal_orchestrator import EnrichedSignal, QuantSignalOrchestrator

# ═══════════════════════════════════════════════════════════════════════════════
# ── Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_enriched_signal(overrides: dict | None = None) -> EnrichedSignal:
    """Create a default EnrichedSignal for integration tests."""
    base = {
        "symbol": "فولاد",
        "name": "فولاد مبارکه",
        "market": "stock",
        "direction": "buy",
        "timeframe": "daily",
        "entry_zone": "50000",
        "stop_loss": "47500",
        "targets": "55000",
        "risk_reward": "2.0",
        "position_sizing": "10%",
        "confirmation_condition": "",
        "reason": "Strong trend with volume confirmation",
        "invalidation": "Break below support",
        "trailing_stop": "",
        "price": 50000,
        "change_pct": 0.5,
        "rule_score": 75.0,
        "ml_score": 0.0,
        "boosted_score": 75.0,
        "ml_influence_pct": 0.0,
        "confidence": 0.70,
        "calibration_level": "high",
        "vote_strategy": "rule_only",
        "vote_direction_scores": {"buy": 1.0},
        "source": "test",
        "created_at": "",
    }
    if overrides:
        base.update(overrides)
    return EnrichedSignal(**base)
def _mock_decision_engine_evaluate(
    verdict: str = "release", grade: str = "A", prob: float = 0.72
):
    """Create a mock decision engine evaluate() with pre-determined results."""
    mock_decision = MagicMock()
    mock_decision.signal_id = "test"
    mock_decision.symbol = "فولاد"
    mock_decision.market = "stock"
    mock_decision.direction = "buy"
    mock_decision.verdict.value = verdict
    mock_decision.is_releasable.return_value = verdict == "release"
    mock_decision.is_watchlisted.return_value = verdict == "watchlist"
    mock_decision.calibrated_probability = prob
    mock_decision.effective_threshold = 0.58
    mock_decision.net_expectancy_r = 0.15
    mock_decision.risk_reward_ratio = 2.0
    mock_decision.fill_probability = 0.8
    mock_decision.verdict = MagicMock()
    mock_decision.verdict.value = verdict
    mock_decision.to_dict.return_value = {"verdict": verdict}
    # Gate results: return list of MagicMock gate result dicts
    mock_decision.gate_results = []


    def _to_dict(g):
        return {
            "gate": g.gate_name,
            "verdict": g.verdict.value if hasattr(g.verdict, "value") else "pass",
            "score": g.score,
            "reason": "",
            "details": {},
        }

    # Create some default gate results
    gate_names = [
        "data_quality",
        "model",
        "probability",
        "regime",
        "consensus",
        "liquidity",
        "risk_reward",
        "expectancy",
        "portfolio",
        "execution",
    ]
    mock_decision.gate_results = [
        MagicMock(
            gate_name=name,
            verdict=MagicMock(value="pass"),
            score=1.0,
            reason="",
            details={},
            to_dict=lambda self=MagicMock(gate_name=name): _to_dict(self),
        )
        for name in gate_names
    ]

    mock_engine = MagicMock()
    mock_engine.evaluate = AsyncMock(return_value=mock_decision)
    mock_engine.signal_grade.return_value = grade
    mock_engine.policy.get_effective_threshold.return_value = prob
    return mock_engine


# ═══════════════════════════════════════════════════════════════════════════════
# ── _apply_signal_decision Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestApplySignalDecision:
    @pytest.mark.asyncio
    async def test_release_signal_stores_decision(self):
        """A released signal should have decision_verdict='release' and a grade."""
        orchestrator = QuantSignalOrchestrator()
        sig = _make_enriched_signal()
        mock_engine = _mock_decision_engine_evaluate(verdict="release", grade="A")
        with patch(
            "services.signal_decision_engine.SignalDecisionEngine",
            return_value=mock_engine,
        ):
            released, rejected = await orchestrator._apply_signal_decision(
                [sig]
            )
        assert len(released) == 1
        assert len(rejected) == 0
        assert released[0].decision_verdict == "release"
        assert released[0].decision_grade == "A"
        assert released[0].calibrated_probability == 0.72
        assert released[0].effective_threshold == 0.58
        assert released[0].net_expectancy_r == 0.15
        assert len(released[0].gate_results) == 10

    @pytest.mark.asyncio
    async def test_rejected_signal_goes_to_rejected_list(self):
        """A rejected signal should go to the rejected list."""
        orchestrator = QuantSignalOrchestrator()
        sig = _make_enriched_signal()
        mock_engine = _mock_decision_engine_evaluate(verdict="reject", grade="REJECT")
        with patch(
            "services.signal_decision_engine.SignalDecisionEngine",
            return_value=mock_engine,
        ):
            released, rejected = await orchestrator._apply_signal_decision(
                [sig]
            )
        assert len(released) == 0
        assert len(rejected) == 1
        assert rejected[0].decision_verdict == "reject"
        assert rejected[0].decision_grade == "REJECT"

    @pytest.mark.asyncio
    async def test_watchlisted_signal_stays_in_released(self):
        """A watchlisted signal should stay in the released list but tagged."""
        orchestrator = QuantSignalOrchestrator()
        sig = _make_enriched_signal()
        mock_engine = _mock_decision_engine_evaluate(
            verdict="watchlist", grade="WATCHLIST"
        )
        with patch(
            "services.signal_decision_engine.SignalDecisionEngine",
            return_value=mock_engine,
        ):
            released, rejected = await orchestrator._apply_signal_decision(
                [sig]
            )
        assert len(released) == 1
        assert len(rejected) == 0
        assert released[0].decision_verdict == "watchlist"
        assert released[0].decision_grade == "WATCHLIST"

    @pytest.mark.asyncio
    async def test_mixed_verdicts_split_correctly(self):
        """Multiple signals with different verdicts should split correctly."""
        orchestrator = QuantSignalOrchestrator()
        sig1 = _make_enriched_signal({"symbol": "فولاد"})
        sig2 = _make_enriched_signal({"symbol": "فملی"})
        sig3 = _make_enriched_signal({"symbol": "وبانک"})
        with patch("services.signal_decision_engine.SignalDecisionEngine") as mock_cls:
            engine_instance = MagicMock()
            # Signal 1 → release (grade A)
            d1 = MagicMock()
            d1.verdict.value = "release"
            d1.calibrated_probability = 0.72
            d1.effective_threshold = 0.58
            d1.net_expectancy_r = 0.15
            d1.risk_reward_ratio = 2.0
            d1.fill_probability = 0.8
            d1.gate_results = [
                MagicMock(to_dict=lambda: {"gate": "test", "verdict": "pass"})
                for _ in range(10)
            ]

            # Signal 2 → reject (grade REJECT)
            d2 = MagicMock()
            d2.verdict.value = "reject"
            d2.calibrated_probability = 0.45
            d2.effective_threshold = 0.58
            d2.net_expectancy_r = -0.1
            d2.risk_reward_ratio = 0.5
            d2.fill_probability = 0.5
            d2.gate_results = [
                MagicMock(to_dict=lambda: {"gate": "test", "verdict": "block"})
                for _ in range(10)
            ]

            # Signal 3 → watchlist (grade WATCHLIST)
            d3 = MagicMock()
            d3.verdict.value = "watchlist"
            d3.calibrated_probability = 0.60
            d3.effective_threshold = 0.55
            d3.net_expectancy_r = 0.03
            d3.risk_reward_ratio = 1.0
            d3.fill_probability = 0.7
            d3.gate_results = [
                MagicMock(to_dict=lambda: {"gate": "test", "verdict": "warn"})
                for _ in range(10)
            ]

            # Set up side_effect to return different decisions
            engine_instance.evaluate = AsyncMock(side_effect=[d1, d2, d3])
            engine_instance.signal_grade = MagicMock(
                side_effect=["A", "REJECT", "WATCHLIST"]
            )
            mock_cls.return_value = engine_instance

            released, rejected = await orchestrator._apply_signal_decision(
                [sig1, sig2, sig3]
            )
        assert len(released) == 2  # sig1 (release) + sig3 (watchlist)
        assert len(rejected) == 1  # sig2 (reject)
        assert released[0].decision_grade == "A"
        assert rejected[0].decision_grade == "REJECT"
        assert released[1].decision_grade == "WATCHLIST"

    @pytest.mark.asyncio
    async def test_empty_signals(self):
        """Empty list should return empty released and rejected."""
        orchestrator = QuantSignalOrchestrator()
        released, rejected = await orchestrator._apply_signal_decision([])
        assert released == []
        assert rejected == []

    @pytest.mark.asyncio
    async def test_signal_with_ml_score_uses_hybrid_mapping(self):
        """Signal with ml_score > 0 should be mapped as signal_type='hybrid'."""
        orchestrator = QuantSignalOrchestrator()
        sig = _make_enriched_signal({"ml_score": 0.72})
        with patch("services.signal_decision_engine.SignalDecisionEngine") as mock_cls:
            engine_instance = MagicMock()
            d = MagicMock()
            d.verdict.value = "release"
            d.calibrated_probability = 0.72
            d.effective_threshold = 0.55
            d.net_expectancy_r = 0.20
            d.risk_reward_ratio = 2.0
            d.fill_probability = 0.8
            d.gate_results = [
                MagicMock(to_dict=lambda: {"gate": "test"}) for _ in range(10)
            ]
            engine_instance.evaluate = AsyncMock(return_value=d)
            engine_instance.signal_grade.return_value = "A"
            mock_cls.return_value = engine_instance

            released, _rejected = await orchestrator._apply_signal_decision(
                [sig]
            )
        assert len(released) == 1
        # The mock engine should have received a SignalCandidate with signal_type='hybrid'
        # We can verify this by checking the call args
        call_args = engine_instance.evaluate.call_args
        assert call_args is not None
        candidate = call_args[0][0]
        assert candidate.signal_type == "hybrid"
        assert candidate.active_models == 1
        assert candidate.agreeing_models == 1

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_engine_failure(self):
        """When decision engine fails on a signal, keep it as release with grade UNGATED."""
        orchestrator = QuantSignalOrchestrator()
        sig = _make_enriched_signal()
        with patch("services.signal_decision_engine.SignalDecisionEngine") as mock_cls:
            engine_instance = MagicMock()
            engine_instance.evaluate = AsyncMock(side_effect=Exception("Engine crash"))
            engine_instance.signal_grade = MagicMock(
                side_effect=Exception("Grade crash")
            )
            mock_cls.return_value = engine_instance

            released, rejected = await orchestrator._apply_signal_decision(
                [sig]
            )
        assert len(released) == 1
        assert len(rejected) == 0
        assert released[0].decision_verdict == "release"
        assert released[0].decision_grade == "UNGATED"

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_batch_failure(self):
        """When the entire decision engine initialization fails, release all signals."""
        orchestrator = QuantSignalOrchestrator()
        sig = _make_enriched_signal()
        with patch(
            "services.signal_decision_engine.SignalDecisionEngine",
            side_effect=Exception("Init crash"),
        ):
            released, rejected = await orchestrator._apply_signal_decision(
                [sig]
            )
        assert len(released) == 1
        assert len(rejected) == 0
        assert released[0].decision_verdict == "release"
        assert released[0].decision_grade == "UNGATED"
