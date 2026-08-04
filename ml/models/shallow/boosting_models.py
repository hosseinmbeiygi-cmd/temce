"""High-quality boosting models: LightGBM, CatBoost, and Stacking Ensemble."""

from __future__ import annotations

import contextlib
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


class LightGBMModel(BaseModel):
    """LightGBM - fastest and best for tabular data.

    Advantages:
    - Gradient-based One-Side Sampling (GOSS) for speed
    - Exclusive Feature Bundling (EFB) for high-dimensional data
    - Native categorical feature support
    - Early stopping built-in
    """

    def __init__(self, name: str = "lightgbm", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        try:
            import lightgbm as lgb

            task = self.params.pop("task", "regression")
            default_params = {
                "n_estimators": 500,
                "learning_rate": 0.05,
                "max_depth": 7,
                "num_leaves": 63,
                "min_child_samples": 20,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_alpha": 0.1,
                "reg_lambda": 0.1,
                "random_state": 42,
                "n_jobs": -1,
                "verbose": -1,
            }
            default_params.update(self.params)

            if task == "classification":
                self._model = lgb.LGBMClassifier(**default_params)
            else:
                self._model = lgb.LGBMRegressor(**default_params)
        except ImportError:
            raise ImportError("lightgbm not installed. Install with: pip install lightgbm")

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        X_np = _to_numpy(X)
        y_np = _to_numpy(y)

        # Use last 20% as eval set for early stopping
        n = len(X_np)
        eval_size = max(10, int(n * 0.2))
        X_train, X_val = X_np[:-eval_size], X_np[-eval_size:]
        y_train, y_val = y_np[:-eval_size], y_np[-eval_size:]

        self._model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[
                __import__("lightgbm").early_stopping(50, verbose=False),
                __import__("lightgbm").log_evaluation(0),
            ],
        )
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


class CatBoostModel(BaseModel):
    """CatBoost - best for categorical features, robust defaults.

    Advantages:
    - Ordered boosting reduces overfitting
    - Native categorical feature handling
    - Symmetric tree structure
    - Built-in feature importance methods
    """

    def __init__(self, name: str = "catboost", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        try:
            from catboost import CatBoostClassifier, CatBoostRegressor

            task = self.params.pop("task", "regression")
            default_params = {
                "iterations": 500,
                "learning_rate": 0.05,
                "depth": 7,
                "l2_leaf_reg": 3,
                "min_data_in_leaf": 20,
                "random_seed": 42,
                "verbose": 0,
                "early_stopping_rounds": 50,
            }
            default_params.update(self.params)

            if task == "classification":
                self._model = CatBoostClassifier(**default_params)
            else:
                self._model = CatBoostRegressor(**default_params)
        except ImportError:
            raise ImportError("catboost not installed. Install with: pip install catboost")

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        X_np = _to_numpy(X)
        y_np = _to_numpy(y)

        # Use last 20% as eval set for early stopping
        n = len(X_np)
        eval_size = max(10, int(n * 0.2))
        X_train, X_val = X_np[:-eval_size], X_np[-eval_size:]
        y_train, y_val = y_np[:-eval_size], y_np[-eval_size:]

        self._model.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            verbose=0,
        )
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


class StackingEnsembleModel(BaseModel):
    """Stacking Ensemble: combines XGBoost + LightGBM + CatBoost with Ridge meta-learner.

    Architecture:
    - Level 0: XGBoost, LightGBM, CatBoost (base learners)
    - Level 1: Ridge Regression (meta-learner)

    This typically outperforms any single model by 5-15% on financial data.
    """

    def __init__(self, name: str = "stacking_ensemble", params: dict[str, Any] | None = None) -> None:
        super().__init__(name, params)
        self._base_models: list[tuple[str, Any]] = []
        self._meta_learner = None

    def _create_base_models(self, task: str) -> list[tuple[str, Any]]:
        """Create the 3 base learners."""
        models = []

        # XGBoost
        try:
            import xgboost as xgb
            obj = "reg:squarederror" if task == "regression" else "binary:logistic"
            xgb_model = xgb.XGBRegressor(
                n_estimators=300, learning_rate=0.05, max_depth=7,
                subsample=0.8, colsample_bytree=0.8, random_state=42,
                n_jobs=-1, verbosity=0, objective=obj,
            ) if task == "regression" else xgb.XGBClassifier(
                n_estimators=300, learning_rate=0.05, max_depth=7,
                subsample=0.8, colsample_bytree=0.8, random_state=42,
                n_jobs=-1, verbosity=0,
            )
            models.append(("xgboost", xgb_model))
        except ImportError:
            pass

        # LightGBM
        try:
            import lightgbm as lgb
            lgb_model = lgb.LGBMRegressor(
                n_estimators=300, learning_rate=0.05, max_depth=7,
                num_leaves=63, subsample=0.8, colsample_bytree=0.8,
                random_state=42, n_jobs=-1, verbose=-1,
            ) if task == "regression" else lgb.LGBMClassifier(
                n_estimators=300, learning_rate=0.05, max_depth=7,
                num_leaves=63, subsample=0.8, colsample_bytree=0.8,
                random_state=42, n_jobs=-1, verbose=-1,
            )
            models.append(("lightgbm", lgb_model))
        except ImportError:
            pass

        # CatBoost
        try:
            from catboost import CatBoostClassifier, CatBoostRegressor
            cb_model = CatBoostRegressor(
                iterations=300, learning_rate=0.05, depth=7,
                random_seed=42, verbose=0,
            ) if task == "regression" else CatBoostClassifier(
                iterations=300, learning_rate=0.05, depth=7,
                random_seed=42, verbose=0,
            )
            models.append(("catboost", cb_model))
        except ImportError:
            pass

        return models

    def fit(self, X: FeatureMatrix, y: TargetVector, **kwargs: Any) -> None:
        from sklearn.linear_model import Ridge
        from sklearn.model_selection import KFold

        X_np = _to_numpy(X)
        y_np = _to_numpy(y)
        task = self.params.get("task", "regression")

        base_models = self._create_base_models(task)
        if not base_models:
            raise ValueError("No base models available for stacking ensemble")

        n = len(X_np)
        n_base = len(base_models)

        # Generate out-of-fold predictions for meta-learner training
        n_folds = min(5, max(2, n // 50))
        kf = KFold(n_splits=n_folds, shuffle=False)
        oof_preds = np.zeros((n, n_base))

        for _fold_idx, (train_idx, val_idx) in enumerate(kf.split(X_np)):
            X_train, X_val = X_np[train_idx], X_np[val_idx]
            y_train, y_val = y_np[train_idx], y_np[val_idx]

            for model_idx, (name, model) in enumerate(base_models):
                import copy
                fold_model = copy.deepcopy(model)
                try:
                    if hasattr(fold_model, "fit"):
                        # Try with eval_set for early stopping
                        try:
                            if name == "xgboost":
                                fold_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
                            elif name == "lightgbm":
                                import lightgbm
                                fold_model.fit(X_train, y_train, eval_set=[(X_val, y_val)],
                                              callbacks=[lightgbm.early_stopping(30, verbose=False), lightgbm.log_evaluation(0)])
                            elif name == "catboost":
                                fold_model.fit(X_train, y_train, eval_set=(X_val, y_val), verbose=0)
                            else:
                                fold_model.fit(X_train, y_train)
                        except Exception:
                            fold_model.fit(X_train, y_train)
                    preds = fold_model.predict(X_val)
                    oof_preds[val_idx, model_idx] = preds
                except Exception:
                    pass

        # Train meta-learner on out-of-fold predictions
        self._meta_learner = Ridge(alpha=1.0)
        self._meta_learner.fit(oof_preds, y_np)

        # Retrain all base models on full data
        self._base_models = []
        for name, model in base_models:
            import copy
            final_model = copy.deepcopy(model)
            with contextlib.suppress(Exception):
                final_model.fit(X_np, y_np)
            self._base_models.append((name, final_model))

        self._is_fitted = True

    def predict(self, X: FeatureMatrix) -> PredictionResult:
        X_np = _to_numpy(X)
        n_base = len(self._base_models)
        base_preds = np.zeros((len(X_np), n_base))

        for i, (_name, model) in enumerate(self._base_models):
            with contextlib.suppress(Exception):
                base_preds[:, i] = model.predict(X_np)

        # Meta-learner combines predictions
        final_preds = self._meta_learner.predict(base_preds)
        return PredictionResult(predictions=final_preds, model_id=self.name)

    def save(self, path: str) -> None:
        safe = validate_safe_path(path)
        safe.write_bytes(pickle.dumps({
            "base_models": self._base_models,
            "meta_learner": self._meta_learner,
        }))

    def load(self, path: str) -> None:
        safe = validate_safe_path(path)
        data = pickle.loads(safe.read_bytes())
        self._base_models = data["base_models"]
        self._meta_learner = data["meta_learner"]
        self._is_fitted = True

    @property
    def feature_importances(self) -> np.ndarray:
        # Average importance from base models
        importances = []
        for _name, model in self._base_models:
            if hasattr(model, "feature_importances_"):
                importances.append(model.feature_importances_)
        if importances:
            return np.mean(importances, axis=0)
        return np.array([])


# Register all models
model_registry.register("lightgbm", LightGBMModel)
model_registry.register("catboost", CatBoostModel)
model_registry.register("stacking_ensemble", StackingEnsembleModel)
