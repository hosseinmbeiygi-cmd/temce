"""Signal Voting System — combines rule-based signals with ML predictions
and Smart Money analysis to produce a final voted signal with calibrated confidence.

Voting strategies:
  - unanimous: all models + rules + SMC agree (highest confidence)
  - majority: simple majority wins
  - weighted: weighted by historical accuracy
  - ml_override: ML overrides rules when confidence > threshold

Smart Money (SMC) integration:
  - Accumulation + high breakout_readiness → buy bias
  - Distribution + low breakout_readiness → sell bias
  - SMC score weights the vote proportionally
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging import get_logger
from services.ml_signal_connector import MLSignalConnector
from services.multi_market_signal_engine import MarketSignal

logger = get_logger(__name__)


@dataclass
class VoteResult:
    """Result of voting between rule-based and ML signals."""
    final_direction: str          # buy / sell / hold
    final_score: float            # 0-100
    final_confidence: float       # 0-1
    direction_votes: dict[str, float]  # direction -> total weight
    vote_counts: dict[str, int]
    sources_contributing: list[dict[str, Any]]
    ml_weight: float              # How much ML influenced the result (0-1)
    strategy: str                 # unanimous / majority / weighted / ml_override


class SignalVotingSystem:
    """Combines signals from multiple sources with configurable voting strategies."""

    def __init__(self, ml_connector: MLSignalConnector | None = None) -> None:
        self._ml = ml_connector or MLSignalConnector()

    async def vote(
        self,
        rule_signal: MarketSignal,
        ml_prediction: dict[str, Any] | None = None,
        symbol_history: dict[str, Any] | None = None,
        smart_money_analysis: dict[str, Any] | None = None,
        strategy: str = "weighted",
        ml_override_threshold: float = 0.75,
    ) -> VoteResult:
        """Run voting between rule-based signal, ML prediction, and Smart Money analysis.

        Smart Money (SMC) analysis is extracted from SmartMoneyService.analyze() output.
        Adds a weighted vote based on accumulation/distribution phase + breakout readiness.
        """
        sources: list[dict[str, Any]] = []

        # 1. Rule-based vote
        rule_score = rule_signal.score / 100.0  # normalize to 0-1
        rule_direction = rule_signal.direction
        rule_confidence = rule_signal.confidence

        sources.append({
            "source": rule_signal.source,
            "type": "rule_based",
            "direction": rule_direction,
            "score": rule_score,
            "confidence": rule_confidence,
            "strength": rule_signal.strength,
        })

        # 2. ML vote (if available)
        ml_weight = 0.0
        if ml_prediction and ml_prediction.get("models_used"):
            ml_direction = ml_prediction.get("direction", "hold")
            ml_score = ml_prediction.get("ml_score", 0.5)
            ml_confidence = ml_prediction.get("confidence", 0.0)

            sources.append({
                "source": "ml_ensemble",
                "type": "ml",
                "direction": ml_direction,
                "score": ml_score,
                "confidence": ml_confidence,
                "models_used": ml_prediction.get("models_used", []),
            })

            # Adaptive weighting based on ML confidence
            ml_weight = ml_confidence * 0.7  # max 70% ML influence (was 40% — raised to fix weak signal issue #4)

        # 3. Historical accuracy vote (if available)
        if symbol_history:
            hist_accuracy = symbol_history.get("accuracy_pct", 50) / 100.0
            hist_direction = symbol_history.get("best_direction", "hold")

            if hist_accuracy > 0.55:  # only if historically better than random
                sources.append({
                    "source": "historical_accuracy",
                    "type": "historical",
                    "direction": hist_direction,
                    "score": hist_accuracy,
                    "confidence": hist_accuracy * 0.8,
                    "sample_size": symbol_history.get("total", 0),
                })

        # 4. Smart Money analysis vote (if available)
        if smart_money_analysis:
            smc_vote = self._smart_money_to_vote(smart_money_analysis)
            if smc_vote is not None:
                sources.append(smc_vote)

        # ── Execute voting strategy ──
        if strategy == "unanimous":
            return self._unanimous_vote(sources, rule_score, ml_weight)
        elif strategy == "ml_override":
            return self._ml_override_vote(sources, rule_signal, ml_prediction, ml_override_threshold)
        else:
            return self._weighted_vote(sources, rule_score, ml_weight, rule_confidence)

    def _weighted_vote(
        self,
        sources: list[dict[str, Any]],
        rule_score: float,
        ml_weight: float,
        rule_confidence: float,
    ) -> VoteResult:
        """Weighted voting based on confidence and historical accuracy."""
        direction_weights: dict[str, float] = {"buy": 0.0, "sell": 0.0, "hold": 0.0}
        direction_counts: dict[str, int] = {"buy": 0, "sell": 0, "hold": 0}
        total_weight = 0.0

        for src in sources:
            direction = src.get("direction", "hold")
            weight = src.get("confidence", 0.5)
            src_type = src.get("type", "rule_based")

            # Adjust weight by source type
            if src_type == "rule_based":
                weight *= (1.0 - ml_weight * 0.5)  # reduce rule weight when ML is confident
            elif src_type == "ml":
                weight *= ml_weight * 2  # amplify ML weight
            elif src_type == "historical":
                weight *= 0.3  # historical is a weak signal
            elif src_type == "smart_money":
                smc_score = src.get("score", 0.5)
                smc_confidence = src.get("engine_confidence", 0.5)
                weight *= 0.25 + smc_score * 0.3 + smc_confidence * 0.2  # 0.25-0.75x SMC weight

            direction_weights[direction] = direction_weights.get(direction, 0) + weight
            direction_counts[direction] = direction_counts.get(direction, 0) + 1
            total_weight += weight

        # Find winner
        final_direction = max(direction_weights, key=lambda k: direction_weights.get(k, 0))
        final_score = direction_weights[final_direction] / max(total_weight, 0.001) * 100

        # Confidence = how decisive the vote was
        sorted_weights = sorted(direction_weights.values(), reverse=True)
        margin = (sorted_weights[0] - sorted_weights[1]) / max(total_weight, 0.001) if len(sorted_weights) >= 2 else 1.0
        final_confidence = min(1.0, max(0.0, margin))

        # Determine strategy label
        if ml_weight > 0.5:
            strategy_label = "ml_weighted"
        elif len(sources) >= 2 and all(s.get("direction") == final_direction for s in sources):
            strategy_label = "unanimous"
        else:
            strategy_label = "weighted"

        return VoteResult(
            final_direction=final_direction,
            final_score=min(100, max(0, final_score)),
            final_confidence=final_confidence,
            direction_votes=direction_weights,
            vote_counts=direction_counts,
            sources_contributing=sources,
            ml_weight=ml_weight,
            strategy=strategy_label,
        )

    def _unanimous_vote(
        self,
        sources: list[dict[str, Any]],
        rule_score: float,
        ml_weight: float,
    ) -> VoteResult:
        """All sources must agree. If not, default to hold with warning."""
        directions = {s.get("direction", "hold") for s in sources}

        if len(directions) == 1:
            direction = directions.pop()
            avg_confidence = sum(s.get("confidence", 0.5) for s in sources) / max(len(sources), 1)
            return VoteResult(
                final_direction=direction,
                final_score=min(100, rule_score * 100),
                final_confidence=min(1.0, avg_confidence * 1.2),  # bonus for unanimity
                direction_votes={direction: 1.0},
                vote_counts={direction: len(sources)},
                sources_contributing=sources,
                ml_weight=ml_weight,
                strategy="unanimous",
            )

        # Disagreement — default to hold with reduced confidence
        return VoteResult(
            final_direction="hold",
            final_score=50.0,
            final_confidence=0.2,
            direction_votes=dict.fromkeys(directions, 0.0),
            vote_counts={},
            sources_contributing=sources,
            ml_weight=ml_weight,
            strategy="unanimous_disagreement",
        )

    def _ml_override_vote(
        self,
        sources: list[dict[str, Any]],
        rule_signal: MarketSignal,
        ml_prediction: dict[str, Any] | None,
        override_threshold: float,
    ) -> VoteResult:
        """ML overrides rules when ML confidence exceeds threshold."""
        if not ml_prediction or not ml_prediction.get("models_used"):
            # No ML available — fall back to rule-based
            return VoteResult(
                final_direction=rule_signal.direction,
                final_score=rule_signal.score,
                final_confidence=rule_signal.confidence * 0.8,
                direction_votes={rule_signal.direction: 1.0},
                vote_counts={rule_signal.direction: 1},
                sources_contributing=sources,
                ml_weight=0.0,
                strategy="rule_only",
            )

        ml_confidence = ml_prediction.get("confidence", 0.0)
        ml_direction = ml_prediction.get("direction", "hold")

        if ml_confidence >= override_threshold:
            # ML override
            return VoteResult(
                final_direction=ml_direction,
                final_score=ml_prediction.get("ml_score", 0.5) * 100,
                final_confidence=ml_confidence,
                direction_votes={ml_direction: ml_confidence},
                vote_counts={ml_direction: 1},
                sources_contributing=sources,
                ml_weight=1.0,
                strategy="ml_override",
            )

        # ML not confident enough — use weighted vote
        return self._weighted_vote(
            sources,
            rule_signal.score / 100.0,
            ml_confidence * 0.3,
            rule_signal.confidence,
        )

    # ── Smart Money Analysis → Vote Adapter ──────────────────────────

    @staticmethod
    def _smart_money_to_vote(
        smc_analysis: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Convert SmartMoneyService.analyze() output to a vote source dict.

        Maps:
          - Phase "accumulation" / "re-accumulation" → buy bias
          - Phase "distribution" / "re-distribution" → sell bias
          - breakout_readiness amplifies or weakens the signal
          - SMC score (0-1) sets the base confidence
        """
        smc_score = smc_analysis.get("smart_money_score", 0.0)
        if smc_score == 0.0:
            return None  # no valid SMC data

        phase = smc_analysis.get("phase", "neutral")
        scores = smc_analysis.get("scores", {})
        meta = smc_analysis.get("meta", {})
        confidence_data = meta.get("confidence", {})

        accumulation = scores.get("accumulation", 0.5)
        absorption = scores.get("absorption", 0.5)
        breakout_ready = scores.get("breakout_readiness", 0.5)
        buyer_power = scores.get("buyer_power", 0.5)
        microstructure = scores.get("microstructure", 0.5)

        # Determine direction from phase + breakout readiness
        buy_phases = {"accumulation", "re-accumulation", "markup"}
        sell_phases = {"distribution", "re-distribution", "markdown"}

        if phase in buy_phases and breakout_ready > 0.5:
            direction = "buy"
            base_confidence = smc_score * 0.7 + breakout_ready * 0.3
        elif phase in sell_phases and breakout_ready < 0.5:
            direction = "sell"
            base_confidence = smc_score * 0.7 + (1.0 - breakout_ready) * 0.3
        elif accumulation > 0.6 and buyer_power > 0.6:
            direction = "buy"
            base_confidence = accumulation * 0.5 + buyer_power * 0.3 + smc_score * 0.2
        elif absorption > 0.6 and microstructure < 0.4:
            direction = "sell"
            base_confidence = absorption * 0.5 + (1.0 - microstructure) * 0.3 + smc_score * 0.2
        else:
            direction = "hold"
            base_confidence = 0.3 + smc_score * 0.3

        # Cap and apply confidence adjustment
        base_confidence = min(0.95, max(0.05, base_confidence))

        # Quality adjustment from engine confidence
        engine_confidence = confidence_data.get("score", 0.5)
        final_confidence = base_confidence * (0.5 + engine_confidence * 0.5)

        return {
            "source": "smart_money_engine",
            "type": "smart_money",
            "direction": direction,
            "score": smc_score,
            "confidence": round(final_confidence, 4),
            "phase": phase,
            "breakout_readiness": breakout_ready,
            "buyer_power": buyer_power,
            "engine_confidence": engine_confidence,
        }

    def apply_vote_to_signal(self, signal: MarketSignal, vote: VoteResult) -> MarketSignal:
        """Apply the vote result back to a MarketSignal, updating its fields."""
        import copy
        updated = copy.copy(signal)

        updated.direction = vote.final_direction
        updated.score = vote.final_score
        updated.confidence = vote.final_confidence
        updated.strength = vote.final_confidence * (vote.final_score / 100.0)
        updated.source = f"voting_{vote.strategy}"

        # Add voting info to reason
        sources_str = ", ".join(
            f"{s['source']}: {s['direction']} ({s.get('confidence', 0):.0%})"
            for s in vote.sources_contributing
        )
        updated.reason = f"[{vote.strategy.upper()}] {sources_str} | {signal.reason}"

        return updated
