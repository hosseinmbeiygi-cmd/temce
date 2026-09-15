"""Advanced models: Histogram Gradient Boosting, Extra Trees, Robust models."""

from __future__ import annotations

import pickle
from typing import Any

import numpy as np

from core.paths import validate_safe_path
from ml.models.base import BaseModel
from ml.models.registry import model_registry
from ml.types import FeatureMatrix, PredictionResult, TargetVector


def _to_numpy(data: Any) -> np.ndarray:
    """Convert any data type to numpy array."""
    if isinstance(data, np.ndarray):
        return data
    if hasattr(data, "values"):
        return np.asarray(data.values)
    return np.asarray(data)


class HistGradientBoostingModel(BaseModel):
    """Histogram-based Gradient Boosting (sklearn).

    Advantages:
    - Native NaN handling (no imputation needed)
    - Very fast (histogram-based splitting)
    - Good for large datasets
    - No external dependency (sklearn built-in)
    """

    def __init__(self, name: str = "hist_gradient_boosting", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

        task = self.params.pop("task", "regression")
        default_params = {
            "max_iter": 500,
            "learning_rate": 0.05,
            "max_depth": 7,
            "min_samples_leaf": 20,
            "l2_regularization": 0.1,
            "random_state": 42,
        }
        default_params.update(self.params)

        if task == "classification":
            self._model = HistGradientBoostingClassifier(**default_params)
        else:
            self._model = HistGradientBoostingRegressor(**default_params)

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        X_np = _to_numpy(X)
        y_np = _to_numpy(y)
        self._model.fit(X_np, y_np)
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        X_np = _to_numpy(X)
        preds = self._model.predict(X_np)
        probs = None
        if hasattr(self._model, "predict_proba"):
            probs = self._model.predict_proba(X_np)
        return PredictionResult(predictions=preds, probabilities=probs, model_id=self.name)

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        safe.write_bytes(pickle.dumps(self._model))

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        self._model = pickle.loads(safe.read_bytes())
        self._is_fitted = True

    @property
    def feature_importances(self) -> np.ndarray:
        return self._model.feature_importances_


class ExtraTreesModel(BaseModel):
    """Extra Trees (Extremely Randomized Trees).

    Advantages:
    - More random than Random Forest (better generalization)
    - Faster training (no threshold optimization)
    - Robust to noise
    - Good for high-dimensional data
    """

    def __init__(self, name: str = "extra_trees", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor

        task = self.params.pop("task", "regression")
        default_params = {
            "n_estimators": 500,
            "max_depth": 15,
            "min_samples_split": 10,
            "min_samples_leaf": 5,
            "random_state": 42,
            "n_jobs": -1,
        }
        default_params.update(self.params)

        if task == "classification":
            self._model = ExtraTreesClassifier(**default_params)
        else:
            self._model = ExtraTreesRegressor(**default_params)

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        X_np = _to_numpy(X)
        y_np = _to_numpy(y)
        self._model.fit(X_np, y_np)
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        X_np = _to_numpy(X)
        preds = self._model.predict(X_np)
        probs = None
        if hasattr(self._model, "predict_proba"):
            probs = self._model.predict_proba(X_np)
        return PredictionResult(predictions=preds, probabilities=probs, model_id=self.name)

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        safe.write_bytes(pickle.dumps(self._model))

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        self._model = pickle.loads(safe.read_bytes())
        self._is_fitted = True

    @property
    def feature_importances(self) -> np.ndarray:
        return self._model.feature_importances_


class HuberRegressorModel(BaseModel):
    """Huber Regressor - robust to outliers.

    Advantages:
    - Robust to outliers (uses Huber loss)
    - Good for financial data with fat tails
    - Linear model with robustness
    """

    def __init__(self, name: str = "huber_regressor", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        from sklearn.linear_model import HuberRegressor

        default_params = {"epsilon": 1.35, "max_iter": 200}
        default_params.update(self.params)
        self._model = HuberRegressor(**default_params)

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        X_np = _to_numpy(X)
        y_np = _to_numpy(y)
        self._model.fit(X_np, y_np)
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        X_np = _to_numpy(X)
        preds = self._model.predict(X_np)
        return PredictionResult(predictions=preds, model_id=self.name)

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        safe.write_bytes(pickle.dumps(self._model))

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        self._model = pickle.loads(safe.read_bytes())
        self._is_fitted = True


class BayesianRidgeModel(BaseModel):
    """Bayesian Ridge Regression.

    Advantages:
    - Provides uncertainty estimates
    - Good for small datasets
    - Automatic regularization
    - Robust to multicollinearity
    """

    def __init__(self, name: str = "bayesian_ridge", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        from sklearn.linear_model import BayesianRidge

        self._model = BayesianRidge()

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        X_np = _to_numpy(X)
        y_np = _to_numpy(y)
        self._model.fit(X_np, y_np)
        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        X_np = _to_numpy(X)
        preds, std = self._model.predict(X_np, return_std=True)
        return PredictionResult(
            predictions=preds,
            model_id=self.name,
            metadata={"uncertainty": std},
        )

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        safe.write_bytes(pickle.dumps(self._model))

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        self._model = pickle.loads(safe.read_bytes())
        self._is_fitted = True


# Register all models
model_registry.register("hist_gradient_boosting", HistGradientBoostingModel)
model_registry.register("extra_trees", ExtraTreesModel)
model_registry.register("huber_regressor", HuberRegressorModel)
model_registry.register("bayesian_ridge", BayesianRidgeModel)
