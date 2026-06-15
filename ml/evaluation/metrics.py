from __future__ import annotations

import contextlib

import numpy as np


class MetricsCalculator:
    def compute(self, y_true: np.ndarray, y_pred: np.ndarray, task: str = "regression") -> dict[str, float]:
        if task == "regression":
            return self._regression_metrics(y_true, y_pred)
        return self._classification_metrics(y_true, y_pred)

    def _regression_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        mae = float(mean_absolute_error(y_true, y_pred))
        mse = float(mean_squared_error(y_true, y_pred))
        rmse = float(np.sqrt(mse))
        mape = float(np.mean(np.abs((y_true - y_pred) / (y_true + 1e-10))) * 100)
        r2 = float(r2_score(y_true, y_pred))
        return {"mae": mae, "mse": mse, "rmse": rmse, "mape": mape, "r2": r2}

    def _classification_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

        acc = float(accuracy_score(y_true, y_pred))
        prec = float(precision_score(y_true, y_pred, average="weighted", zero_division=0))
        rec = float(recall_score(y_true, y_pred, average="weighted", zero_division=0))
        f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))
        auc = 0.0
        with contextlib.suppress(Exception):
            auc = float(roc_auc_score(y_true, y_pred, multi_class="ovr"))
        return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "auc": auc}
