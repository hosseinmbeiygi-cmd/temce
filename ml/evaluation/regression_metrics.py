from __future__ import annotations

from typing import Any


class RegressionMetrics:
    def __init__(self, y_true: Any, y_pred: Any) -> None:
        self.y_true = y_true
        self.y_pred = y_pred

    def r2_score(self) -> float:
        from sklearn.metrics import r2_score

        return float(r2_score(self.y_true, self.y_pred))

    def explained_variance(self) -> float:
        from sklearn.metrics import explained_variance_score

        return float(explained_variance_score(self.y_true, self.y_pred))

    def rmse(self) -> float:
        import numpy as np
        from sklearn.metrics import mean_squared_error

        return float(np.sqrt(mean_squared_error(self.y_true, self.y_pred)))
