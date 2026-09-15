from __future__ import annotations

from typing import Any


class ModelInterpreter:
    def feature_importance(self, model: Any) -> dict[str, float] | None:
        if hasattr(model, "feature_importances_"):
            return dict(enumerate(model.feature_importances_))
        if hasattr(model, "coef_"):
            import numpy as np

            return dict(enumerate(np.abs(model.coef_[0])))
        return None

    def permutation_importance(self, model: Any, X: Any, y: Any) -> dict[str, float]:
        from sklearn.inspection import permutation_importance

        result = permutation_importance(model, X, y, n_repeats=10)
        return dict(enumerate(result.importances_mean))
