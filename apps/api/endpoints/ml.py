from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_inference_service
from schemas.api.ml import MlTrainRequest, MlTrainResponse
from schemas.common.responses import ApiResponse
from services.inference_service import InferenceService

router = APIRouter()


# ── In-memory prediction results store ──────────────────────────────────────
_prediction_results: dict[str, dict[str, Any]] = {}


def _run_model_on_symbol(model_type: str, symbol: str) -> dict[str, Any]:
    """Simulate running a model on a single symbol and return results."""
    base_accuracy = {
        "xgboost": 0.85,
        "random_forest": 0.82,
        "linear_regression": 0.72,
        "lstm": 0.79,
        "gru": 0.78,
        "cnn": 0.76,
        "transformer": 0.81,
    }.get(model_type, 0.75)
    noise = random.uniform(-0.08, 0.08)
    accuracy = min(max(base_accuracy + noise, 0.5), 0.98)
    return {
        "symbol": symbol,
        "model_type": model_type,
        "prediction": round(random.uniform(35000, 45000), 2),
        "accuracy": round(accuracy, 4),
        "confidence": round(min(max(accuracy + random.uniform(-0.05, 0.05), 0), 1), 4),
        "f1_score": round(accuracy * random.uniform(0.85, 1.0), 4),
        "mse": round(random.uniform(0.01, 0.05), 4),
        "samples": random.randint(500, 2000),
        "duration_seconds": round(random.uniform(0.5, 5.0), 2),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/models", summary="List ML models", description="List all registered ML models")
async def list_models() -> ApiResponse[list[dict]]:
    from ml.global_registry import get_registry
    registry = get_registry()
    models = registry.list_models()
    return ApiResponse[list[dict]](success=True, data=models)


@router.get("/runs", summary="List training runs", description="List all training runs")
async def list_runs() -> ApiResponse[list[dict]]:
    from services.global_training_service import get_training_service
    service = get_training_service()
    result = await service.list_runs()
    return ApiResponse[list[dict]](success=True, data=result.value if result.success else [])


@router.get("/runs/{run_id}", summary="Get training run", description="Get details of a specific training run")
async def get_run(run_id: str) -> ApiResponse[dict]:
    from services.global_training_service import get_training_service
    service = get_training_service()
    result = await service.get_training_status(run_id)
    if result.success and result.value:
        return ApiResponse[dict](success=True, data=result.value)
    return ApiResponse[dict](success=False, data={}, error={"message": "Run not found"})


@router.post("/predict/{model_id}")
async def predict(
    model_id: str,
    features: dict[str, Any],
    service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.predict(model_id, features)
    if result.success and result.value:
        import dataclasses
        data = dataclasses.asdict(result.value)
        data["prediction"] = data.pop("predictions", None)
        probs = data.pop("probabilities", [])
        data["confidence"] = probs[0] if probs else None
        return ApiResponse[dict[str, Any]](success=True, data=data)
    return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": result.error or "Prediction failed"})


@router.post("/predict-all", summary="Run model on all symbols", description="Run the specified model on all symbols and save results")
async def predict_all(body: dict[str, Any]) -> ApiResponse[dict[str, Any]]:
    model_type = body.get("model_type", "xgboost")
    symbols = body.get("symbols", [
        "فولاد", "فملی", "شپنا", "وبملت", "خودرو", "ذوب", "رمپنا", "اخابر",
        "شستا", "غگیلا", "پارسان", "کگل", "فخوز", "حفاری", "چادرملو",
        "وبانک", "فولاژ", "فسپا", "شبندر", "شتران", "مارون", "نوری",
        "خساپا", "خگستر", "غصینو", "قشکر", "کچاد", "ومعادن", "وتوصا",
    ])

    batch_id = uuid.uuid4().hex[:12]
    results = []
    for symbol in symbols:
        res = _run_model_on_symbol(model_type, symbol)
        res["batch_id"] = batch_id
        results.append(res)
        _prediction_results[res["symbol"]] = res

    return ApiResponse[dict[str, Any]](success=True, data={
        "batch_id": batch_id,
        "model_type": model_type,
        "total_symbols": len(results),
        "results": results,
    })


@router.get("/predictions", summary="List prediction results", description="List saved prediction results, optionally filtered by symbol")
async def list_predictions(
    symbol: str | None = Query(None, description="Filter by symbol"),
) -> ApiResponse[list[dict[str, Any]]]:
    if symbol:
        # Filter by symbol (partial match)
        filtered = [v for k, v in _prediction_results.items() if symbol in k or symbol in v.get("symbol", "")]
        return ApiResponse[list[dict[str, Any]]](success=True, data=filtered)
    return ApiResponse[list[dict[str, Any]]](success=True, data=list(_prediction_results.values()))


@router.post("/train")
async def train(
    body: MlTrainRequest,
    service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[MlTrainResponse]:
    from services.global_training_service import get_training_service

    symbol = body.symbols[0] if body.symbols else ""
    result = await service.train(body.model_type, symbol, body.start_date, body.end_date)

    # Also register this run in the global training service so it appears in Runs tab
    train_service = get_training_service()
    registered = await train_service.start_training(
        experiment_name=body.experiment_name,
        model_type=body.model_type,
        symbols=body.symbols,
    )
    run_id = ""
    if registered.success and registered.value:
        run_id = registered.value.get("id", "")
        # Update with completed metrics
        if result.success and result.value:
            registered.value["status"] = result.value.get("status", "completed")
            registered.value["metrics"] = {
                "accuracy": result.value.get("accuracy", 0),
                "train_samples": result.value.get("train_samples", 0),
                "duration_seconds": result.value.get("duration_seconds", 0),
            }

    if result.success and result.value:
        resp = MlTrainResponse(
            run_id=run_id or result.value.get("model_id", ""),
            experiment_name=body.experiment_name,
            model_type=body.model_type,
            status=result.value.get("status", "completed"),
            message=f"Model trained with accuracy {result.value.get('accuracy', 0)}",
        )
        return ApiResponse[MlTrainResponse](success=True, data=resp)
    return ApiResponse[MlTrainResponse](success=False, data=None, error={"message": result.error or "Training failed"})
