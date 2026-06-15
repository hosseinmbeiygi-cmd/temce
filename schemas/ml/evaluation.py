from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvaluationMetrics(BaseModel):
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    auc_roc: float = 0.0
    mse: float = 0.0
    rmse: float = 0.0
    mae: float = 0.0
    r2_score: float = 0.0
    explained_variance: float = 0.0
    max_error: float = 0.0
    confusion_matrix: dict[str, list[list[int]]] | None = None
    classification_report: dict[str, Any] = Field(default_factory=dict)


class CrossValidationResult(BaseModel):
    fold: int = 0
    metrics: EvaluationMetrics = Field(default_factory=EvaluationMetrics)
    train_size: int = 0
    val_size: int = 0


class EvaluationResult(BaseModel):
    model_name: str = ""
    dataset: str = ""
    metrics: EvaluationMetrics = Field(default_factory=EvaluationMetrics)
    cv_results: list[CrossValidationResult] = Field(default_factory=list)
    feature_importance: dict[str, float] = Field(default_factory=dict)
    predictions_sample: list[dict[str, Any]] = Field(default_factory=list)
    duration_seconds: float = 0.0
    evaluated_at: str = ""
