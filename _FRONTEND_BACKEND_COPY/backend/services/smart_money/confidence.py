"""Confidence Score — estimates uncertainty in the SMC score.

A high SMC score with low confidence means the signal is unreliable
(due to insufficient data, low volume, or high volatility).
This helps users distinguish strong signals from noisy ones.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ConfidenceResult:
    """Confidence assessment for a scoring result."""

    confidence: float = 0.0  # 0.0 = no confidence, 1.0 = high confidence
    data_completeness: float = 0.0  # how complete is the input data
    score_stability: float = 0.0  # how stable are the feature values
    volume_reliability: float = 0.0  # is volume sufficient for reliable analysis
    history_sufficiency: float = 0.0  # is history long enough
    level: str = "low"  # low | medium | high
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class ConfidenceEstimator:
    """Estimates confidence in the SMC score based on data quality and stability."""

    def __init__(
        self,
        min_history_for_high: int = 20,
        min_volume_for_high: int = 500000,
    ) -> None:
        self.min_history_for_high = min_history_for_high
        self.min_volume_for_high = min_volume_for_high

    def estimate(
        self,
        features: dict[str, float],
        history_days: int,
        data_quality_score: float = 1.0,
        analysis_mode: str = "full",
    ) -> ConfidenceResult:
        """Estimate confidence in the scoring result."""
        result = ConfidenceResult()

        # 1. Data completeness (from data quality gate)
        result.data_completeness = data_quality_score

        # 2. History sufficiency
        if history_days >= self.min_history_for_high:
            result.history_sufficiency = 1.0
        elif history_days >= 10:
            result.history_sufficiency = 0.7
        elif history_days >= 5:
            result.history_sufficiency = 0.4
        else:
            result.history_sufficiency = 0.1
            result.warnings.append(f"Insufficient history: {history_days} days")

        # 3. Volume reliability
        rvol_n = features.get("rvol_n", 0.5)
        vtr_n = features.get("vtr_n", 0.5)
        vol_score = (rvol_n + vtr_n) / 2.0
        if vol_score > 0.6:
            result.volume_reliability = min(1.0, vol_score)
        elif vol_score > 0.3:
            result.volume_reliability = vol_score
        else:
            result.volume_reliability = 0.2
            result.warnings.append("Low volume — signals may be unreliable")

        # 4. Score stability — check if features are consistent
        layer_scores = [
            features.get("pvs", 0),
            features.get("abs", 0),
            features.get("fls", 0),
            features.get("ess", 0),
            features.get("rrs", 0),
        ]
        valid_scores = [s for s in layer_scores if s > 0]
        if valid_scores:
            mean_score = sum(valid_scores) / len(valid_scores)
            variance = sum((s - mean_score) ** 2 for s in valid_scores) / len(valid_scores)
            std_dev = math.sqrt(variance)
            # Low std = stable/consistent scores = higher confidence
            result.score_stability = max(0.0, min(1.0, 1.0 - std_dev * 2))
        else:
            result.score_stability = 0.1

        # 5. Analysis mode penalty
        mode_penalty = 1.0 if analysis_mode == "full" else 0.6

        # 6. Composite confidence
        raw_confidence = (
            0.25 * result.data_completeness
            + 0.20 * result.history_sufficiency
            + 0.25 * result.volume_reliability
            + 0.30 * result.score_stability
        ) * mode_penalty

        result.confidence = round(min(1.0, max(0.0, raw_confidence)), 4)

        # 7. Classify level
        if result.confidence >= 0.7:
            result.level = "high"
        elif result.confidence >= 0.4:
            result.level = "medium"
        else:
            result.level = "low"
            result.warnings.append("Low confidence — treat signal with caution")

        return result
