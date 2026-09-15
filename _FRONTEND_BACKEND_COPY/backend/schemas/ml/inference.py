from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InferenceRequest(BaseModel):
    model_name: str
    model_version: str = "latest"
    features: dict[str, Any] = Field(default_factory=dict)
    return_probabilities: bool = False


class InferenceResponse(BaseModel):
    model_name: str = ""
    model_version: str = ""
    prediction: Any = None
    probability: float | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0
    latency_ms: float = 0.0
    feature_importance: dict[str, float] = Field(default_factory=dict)


class BatchInferenceResult(BaseModel):
    request_id: str
    model_name: str = ""
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    duration_seconds: float = 0.0
