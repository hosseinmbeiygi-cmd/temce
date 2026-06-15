from __future__ import annotations

from typing import Any


class ROCEvaluator:
    def __init__(self, y_true: Any, y_score: Any) -> None:
        self.y_true = y_true
        self.y_score = y_score

    def auc(self) -> float:
        from sklearn.metrics import roc_auc_score

        return float(roc_auc_score(self.y_true, self.y_score))

    def curve(self) -> tuple[Any, Any]:
        from sklearn.metrics import roc_curve

        return roc_curve(self.y_true, self.y_score)
