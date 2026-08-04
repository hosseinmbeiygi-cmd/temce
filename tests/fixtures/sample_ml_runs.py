from __future__ import annotations

from datetime import UTC, datetime

from core.ids import new_id


def sample_ml_run(
    run_id: str | None = None,
    experiment_name: str = "test_experiment",
    status: str = "completed",
) -> dict:
    return {
        "id": run_id or new_id("mlrun"),
        "experiment_name": experiment_name,
        "run_name": f"run_{new_id()[:8]}",
        "status": status,
        "model_type": "xgboost",
        "dataset_snapshot": "ds_20240101",
        "metrics": {"accuracy": 0.85, "f1_score": 0.82, "auc_roc": 0.91},
        "params": {"learning_rate": 0.1, "max_depth": 6, "n_estimators": 100},
        "artifacts": {
            "model": "/data/models/xgboost_v1.pkl",
            "features": "/data/features/v1.json",
        },
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "duration_seconds": 120.5,
    }


def sample_ml_model(
    model_id: str | None = None,
    name: str = "test_model",
    task: str = "classification",
) -> dict:
    return {
        "id": model_id or new_id("mlmod"),
        "name": name,
        "task": task,
        "framework": "xgboost",
        "latest_version": "1.0.0",
        "versions": [
            {
                "version": "1.0.0",
                "stage": "production",
                "metrics": {"accuracy": 0.85, "f1_score": 0.82},
                "parameters": {"learning_rate": 0.1},
                "artifact_path": "/data/models/test_model/1.0.0",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ],
        "tags": ["test", "classification"],
    }
