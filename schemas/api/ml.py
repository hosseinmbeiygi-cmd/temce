from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from schemas.api.legal import LegalDisclaimerMixin


class MlPredictionRequest(BaseModel):
    symbol: str
    model_name: str = "default"
    features: dict[str, Any] = Field(default_factory=dict)
    horizon: int = 5


class MlPredictionResponse(BaseModel, LegalDisclaimerMixin):
    symbol: str = ""
    model_name: str = ""
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    feature_importance: dict[str, float] = Field(default_factory=dict)
    generated_at: str = ""


class MlTrainRequest(BaseModel):
    experiment_name: str = "default"
    model_type: str = "xgboost"
    symbols: list[str] = Field(default_factory=list)
    target: str = "price_change_pct"
    features: list[str] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    test_size: float = 0.2


class MlTrainResponse(BaseModel):
    run_id: str
    experiment_name: str = ""
    model_type: str = ""
    status: str = "started"
    message: str = ""
