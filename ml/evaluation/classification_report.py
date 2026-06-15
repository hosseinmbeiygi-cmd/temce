from __future__ import annotations

from typing import Any


class ClassificationReport:
    def __init__(self, y_true: Any, y_pred: Any) -> None:
        self.y_true = y_true
        self.y_pred = y_pred

    def generate(self) -> str:
        from sklearn.metrics import classification_report

        return classification_report(self.y_true, self.y_pred)
