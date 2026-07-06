"""
Global singleton ML model registry with demo seed data.
This module provides a single shared ModelRegistry instance that
is seeded with demo data on first import so the ML dashboard
always has data to display.
"""

from __future__ import annotations

from ml.model_registry import ModelRegistry

def _create_seeded_registry() -> ModelRegistry:
    registry = ModelRegistry()

    m1_id = registry.register("XGBoost Price Predictor", "regression", "xgboost", tags=["price", "featured"])
    registry.add_version(
        m1_id, "v1.0.0",
        metrics={"accuracy": 0.871, "f1": 0.834, "mse": 0.0241, "mae": 0.112, "r2": 0.892},
        stage="production",
    )
    registry.add_version(
        m1_id, "v1.1.0",
        metrics={"accuracy": 0.892, "f1": 0.856, "mse": 0.0187, "mae": 0.098, "r2": 0.914},
        stage="staging",
    )

    m2_id = registry.register("Random Forest Classifier", "classification", "random_forest", tags=["signal", "trend"])
    registry.add_version(
        m2_id, "v2.0.0",
        metrics={"accuracy": 0.843, "f1": 0.812, "mse": 0.0312, "mae": 0.134, "r2": 0.867},
        stage="production",
    )
    registry.add_version(
        m2_id, "v2.1.0",
        metrics={"accuracy": 0.865, "f1": 0.838, "mse": 0.0275, "mae": 0.121, "r2": 0.883},
        stage="development",
    )

    m3_id = registry.register("LSTM Trend Predictor", "regression", "lstm", tags=["deep-learning", "time-series"])
    registry.add_version(
        m3_id, "v1.0.0",
        metrics={"accuracy": 0.794, "f1": 0.762, "mse": 0.0452, "mae": 0.167, "r2": 0.801},
        stage="development",
    )

    registry.register("Linear Regression Baseline", "regression", "linear_regression", tags=["baseline"])

    return registry


# Eager initialization: registry is ready on module import
_registry = _create_seeded_registry()


def get_registry() -> ModelRegistry:
    return _registry
