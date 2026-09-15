"""
Global singleton training service with demo seed data.
Provides a shared TrainingService instance so training runs
persist within the server process.
"""

from __future__ import annotations

from services.training_service import TrainingService


def _create_seeded_service() -> TrainingService:
    import uuid

    service = TrainingService()

    # Seed some demo training runs
    demo_runs = [
        {
            "id": uuid.uuid4().hex[:12],
            "experiment_name": "xgboost-v1-فولاد",
            "model_type": "xgboost",
            "symbols": ["فولاد", "فملی"],
            "status": "completed",
            "metrics": {"accuracy": 0.871, "f1": 0.834, "mse": 0.024, "mae": 0.112, "r2": 0.892},
        },
        {
            "id": uuid.uuid4().hex[:12],
            "experiment_name": "rf-v2-شپنا-وبملت",
            "model_type": "random_forest",
            "symbols": ["شپنا", "وبملت"],
            "status": "completed",
            "metrics": {"accuracy": 0.843, "f1": 0.812, "mse": 0.031, "mae": 0.134, "r2": 0.867},
        },
        {
            "id": uuid.uuid4().hex[:12],
            "experiment_name": "lstm-trend-v1",
            "model_type": "lstm",
            "symbols": ["فملی"],
            "status": "failed",
            "metrics": {"accuracy": 0.0, "f1": 0.0, "mse": 0.0, "mae": 0.0, "r2": 0.0},
        },
    ]
    for run in demo_runs:
        service._runs[run["id"]] = run

    return service


_service = _create_seeded_service()


def get_training_service() -> TrainingService:
    return _service
