from __future__ import annotations

from typing import Any


class ThresholdOptimizer:
    def optimal_threshold(self, y_true: Any, y_score: Any) -> float:
        import numpy as np
        from sklearn.metrics import f1_score

        thresholds = np.linspace(0, 1, 101)
        best_f1 = 0.0
        best_thresh = 0.5
        for t in thresholds:
            preds = (np.array(y_score) >= t).astype(int)
            f1 = f1_score(y_true, preds)
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = t
        return float(best_thresh)

    def apply_threshold(self, y_score: Any, threshold: float) -> Any:
        import numpy as np

        return (np.array(y_score) >= threshold).astype(int)
