from __future__ import annotations

from typing import Any


class LossFunction:
    @staticmethod
    def mse(y_true: Any, y_pred: Any) -> float:
        import numpy as np

        return float(np.mean((np.array(y_true) - np.array(y_pred)) ** 2))

    @staticmethod
    def mae(y_true: Any, y_pred: Any) -> float:
        import numpy as np

        return float(np.mean(np.abs(np.array(y_true) - np.array(y_pred))))

    @staticmethod
    def binary_cross_entropy(y_true: Any, y_pred: Any) -> float:
        import numpy as np

        y_pred = np.clip(np.array(y_pred), 1e-15, 1 - 1e-15)
        return float(-np.mean(np.array(y_true) * np.log(y_pred) + (1 - np.array(y_true)) * np.log(1 - y_pred)))
