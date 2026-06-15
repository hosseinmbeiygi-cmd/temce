from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from core.result import Result
from schemas.ml.inference import InferenceResponse
from schemas.ml.models import ModelDefinition
from schemas.ml.training import TrainingRun

ModelMetaSchema = ModelDefinition
TrainingRunSchema = TrainingRun
PredictionSchema = InferenceResponse

logger = get_logger(__name__)


class MLReportBuilder:
    async def build_model_report(self, model: ModelMetaSchema | dict[str, Any]) -> Result[dict[str, Any]]:
        data_in = model if isinstance(model, dict) else model.model_dump() if hasattr(model, "model_dump") else {}
        data: dict[str, Any] = {
            "title": f"Model Report: {data_in.get('model_id', 'N/A')}",
            "report_type": "ml_model",
            "generated_at": datetime.now(UTC).isoformat(),
            "model_id": data_in.get("model_id", ""),
            "version": data_in.get("version", ""),
            "stage": data_in.get("stage", ""),
            "metrics": data_in.get("metrics", {}),
            "params": data_in.get("params", {}),
            "feature_names": data_in.get("feature_names", []),
            "created_at": str(data_in.get("created_at", "")),
        }
        return Result.ok(data)

    async def build_training_report(self, run: TrainingRunSchema | dict[str, Any]) -> Result[dict[str, Any]]:
        data_in = run if isinstance(run, dict) else run.model_dump() if hasattr(run, "model_dump") else {}
        data: dict[str, Any] = {
            "title": f"Training Run Report: {data_in.get('run_id', 'N/A')}",
            "report_type": "ml_training",
            "generated_at": datetime.now(UTC).isoformat(),
            "run_id": data_in.get("run_id", ""),
            "model_name": data_in.get("model_name", ""),
            "status": data_in.get("status", ""),
            "metrics": data_in.get("metrics", {}),
            "params": data_in.get("params", {}),
            "started_at": str(data_in.get("started_at", "")),
            "completed_at": str(data_in.get("completed_at", "")),
        }
        return Result.ok(data)

    async def build_prediction_report(self, predictions: PredictionSchema | dict[str, Any]) -> Result[dict[str, Any]]:
        if isinstance(predictions, dict):
            data_in = predictions
        else:
            data_in = predictions.model_dump() if hasattr(predictions, "model_dump") else {}
        data: dict[str, Any] = {
            "title": "Prediction Report",
            "report_type": "ml_prediction",
            "generated_at": datetime.now(UTC).isoformat(),
            "model_id": data_in.get("model_id", ""),
            "predictions": data_in.get("predictions", []),
            "probabilities": data_in.get("probabilities"),
            "timestamp": str(data_in.get("timestamp", "")),
        }
        return Result.ok(data)
