"""
Global singleton ML model registry.

MLD-01: In production (`settings.is_production == True`) this module returns
an empty DemoModelRegistry so the dashboard shows real data or nothing — never
fabricated metrics with stage="production".  Demo seed data is only used in
development/test environments where it makes rapid iteration easier.
"""

from __future__ import annotations

from ml.model_registry import DemoModelRegistry


def _create_seeded_registry() -> DemoModelRegistry:
    """Return a registry pre-seeded with demo data (dev/test only)."""
    registry = DemoModelRegistry()

    m1_id = registry.register("XGBoost Price Predictor", "regression", "xgboost", tags=["price", "featured"])
    registry.add_version(
        m1_id, "v1.0.0",
        metrics={"accuracy": 0.871, "f1": 0.834, "mse": 0.0241, "mae": 0.112, "r2": 0.892},
        stage="development",
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
        stage="development",
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


def _make_registry() -> DemoModelRegistry:
    """Return the right registry for the current environment (MLD-01)."""
    try:
        from core.config import settings as _settings
        if _settings.is_production:
            # Production: empty registry — dashboard shows real DB data or nothing.
            return DemoModelRegistry()
    except Exception:
        pass
    return _create_seeded_registry()


# Eager initialization: registry is ready on module import
_registry = _make_registry()


def get_registry() -> DemoModelRegistry:
    return _registry
