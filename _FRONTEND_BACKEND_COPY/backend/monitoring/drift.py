from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DriftResult:
    metric_name: str
    drift_score: float
    is_drifted: bool
    threshold: float
    details: dict[str, Any] = field(default_factory=dict)


class DriftDetector:
    def __init__(self) -> None:
        self._drift_history: list[dict[str, Any]] = []

    def _mean(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _std_dev(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = self._mean(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def _ks_distance(self, sample_a: list[float], sample_b: list[float]) -> float:
        if not sample_a or not sample_b:
            return 0.0
        all_values = sorted(set(sample_a + sample_b))
        max_distance = 0.0
        n_a = len(sample_a)
        n_b = len(sample_b)
        for val in all_values:
            cdf_a = sum(1 for x in sample_a if x <= val) / n_a
            cdf_b = sum(1 for x in sample_b if x <= val) / n_b
            distance = abs(cdf_a - cdf_b)
            if distance > max_distance:
                max_distance = distance
        return max_distance

    def _psi(self, reference: list[float], current: list[float], bins: int = 10) -> float:
        if not reference or not current:
            return 0.0
        min_val = min(min(reference), min(current))
        max_val = max(max(reference), max(current))
        if min_val == max_val:
            return 0.0
        [min_val + (max_val - min_val) * i / bins for i in range(bins + 1)]
        ref_counts = [0] * bins
        cur_counts = [0] * bins
        for val in reference:
            idx = min(int((val - min_val) / (max_val - min_val) * (bins - 1)), bins - 1)
            ref_counts[idx] += 1
        for val in current:
            idx = min(int((val - min_val) / (max_val - min_val) * (bins - 1)), bins - 1)
            cur_counts[idx] += 1
        n_ref = len(reference)
        n_cur = len(current)
        psi = 0.0
        for r, c in zip(ref_counts, cur_counts, strict=False):
            p_ref = r / n_ref if n_ref > 0 else 0
            p_cur = c / n_cur if n_cur > 0 else 0
            if p_ref > 0 and p_cur > 0:
                psi += (p_cur - p_ref) * math.log(p_cur / p_ref)
        return psi

    def detect_data_drift(
        self,
        reference_data: list[float],
        current_data: list[float],
        threshold: float = 0.1,
    ) -> DriftResult:
        ks_distance = self._ks_distance(reference_data, current_data)
        psi_score = self._psi(reference_data, current_data)
        ref_mean = self._mean(reference_data)
        cur_mean = self._mean(current_data)
        ref_std = self._std_dev(reference_data)
        cur_std = self._std_dev(current_data)
        mean_shift = abs(cur_mean - ref_mean) / ref_std if ref_std > 0 else 0.0
        drift_score = max(ks_distance, psi_score, mean_shift)
        is_drifted = drift_score > threshold
        result = DriftResult(
            metric_name="data_drift",
            drift_score=round(drift_score, 6),
            is_drifted=is_drifted,
            threshold=threshold,
            details={
                "ks_distance": round(ks_distance, 6),
                "psi": round(psi_score, 6),
                "mean_shift": round(mean_shift, 6),
                "reference_mean": round(ref_mean, 6),
                "current_mean": round(cur_mean, 6),
                "reference_std": round(ref_std, 6),
                "current_std": round(cur_std, 6),
            },
        )
        self._drift_history.append(
            {
                "result_id": uuid.uuid4().hex[:8],
                "metric_name": result.metric_name,
                "drift_score": result.drift_score,
                "is_drifted": result.is_drifted,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        logger.info(
            "Data drift detection: score=%.6f, drifted=%s, threshold=%.6f",
            drift_score,
            is_drifted,
            threshold,
        )
        return result

    def detect_prediction_drift(
        self,
        historical_predictions: list[float],
        recent_predictions: list[float],
        threshold: float = 0.15,
    ) -> DriftResult:
        ks_distance = self._ks_distance(historical_predictions, recent_predictions)
        psi_score = self._psi(historical_predictions, recent_predictions)
        hist_mean = self._mean(historical_predictions)
        recent_mean = self._mean(recent_predictions)
        hist_std = self._std_dev(historical_predictions)
        recent_std = self._std_dev(recent_predictions)
        mean_shift = abs(recent_mean - hist_mean) / hist_std if hist_std > 0 else 0.0
        std_ratio = recent_std / hist_std if hist_std > 0 else 1.0
        drift_score = max(ks_distance, psi_score, mean_shift)
        is_drifted = drift_score > threshold
        result = DriftResult(
            metric_name="prediction_drift",
            drift_score=round(drift_score, 6),
            is_drifted=is_drifted,
            threshold=threshold,
            details={
                "ks_distance": round(ks_distance, 6),
                "psi": round(psi_score, 6),
                "mean_shift": round(mean_shift, 6),
                "std_ratio": round(std_ratio, 6),
                "historical_mean": round(hist_mean, 6),
                "recent_mean": round(recent_mean, 6),
                "historical_std": round(hist_std, 6),
                "recent_std": round(recent_std, 6),
            },
        )
        self._drift_history.append(
            {
                "result_id": uuid.uuid4().hex[:8],
                "metric_name": result.metric_name,
                "drift_score": result.drift_score,
                "is_drifted": result.is_drifted,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        logger.info(
            "Prediction drift detection: score=%.6f, drifted=%s, threshold=%.6f",
            drift_score,
            is_drifted,
            threshold,
        )
        return result

    def get_drift_report(self) -> dict[str, Any]:
        total_checks = len(self._drift_history)
        drifted_count = sum(1 for r in self._drift_history if r["is_drifted"])
        recent_drifts = [r for r in self._drift_history if r["is_drifted"]][-10:]
        return {
            "total_checks": total_checks,
            "drifted_count": drifted_count,
            "drift_rate": round(drifted_count / total_checks, 4) if total_checks > 0 else 0.0,
            "recent_drifts": recent_drifts,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def reset(self) -> None:
        self._drift_history.clear()


drift_detector = DriftDetector()
