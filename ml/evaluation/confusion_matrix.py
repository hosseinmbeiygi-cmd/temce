from __future__ import annotations

from typing import Any


class ConfusionMatrix:
    def __init__(self, y_true: Any, y_pred: Any) -> None:
        self.y_true = y_true
        self.y_pred = y_pred

    def compute(self) -> Any:
        from sklearn.metrics import confusion_matrix

        return confusion_matrix(self.y_true, self.y_pred)
