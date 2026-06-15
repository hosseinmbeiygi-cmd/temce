from __future__ import annotations

from typing import Any


class DriftDetector:
    def __init__(self, reference_data: Any | None = None) -> None:
        self.reference_data = reference_data

    def detect_drift(self, new_data: Any) -> dict[str, float]:
        import numpy as np

        if self.reference_data is None:
            return {"drift_score": 0.0, "drifted": False}
        ref_mean = np.mean(self.reference_data)
        new_mean = np.mean(new_data)
        drift = float(abs(new_mean - ref_mean) / (ref_mean + 1e-8))
        return {"drift_score": drift, "drifted": drift > 0.1}
