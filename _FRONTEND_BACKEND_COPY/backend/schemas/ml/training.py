from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HyperparameterGrid(BaseModel):
    param_name: str
    param_type: str = "float"
    values: list[Any] = Field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None


class TrainingConfig(BaseModel):
    model_type: str = "xgboost"
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    dataset_config: dict[str, Any] = Field(default_factory=dict)
    cv_folds: int = 3
    test_size: float = 0.2
    random_seed: int = 42
    early_stopping_rounds: int = 10
    max_training_time_minutes: int = 60


class TrainingRun(BaseModel):
    id: str
    experiment_name: str = "default"
    run_name: str = ""
    status: str = "pending"
    config: TrainingConfig = Field(default_factory=TrainingConfig)
    metrics: dict[str, float] = Field(default_factory=dict)
    best_params: dict[str, Any] = Field(default_factory=dict)
    model_artifact_path: str = ""
    progress_pct: float = 0.0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    error: str | None = None
    created_at: datetime | None = None
