from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_inference_service
from schemas.api.ml import MlTrainRequest, MlTrainResponse
from schemas.common.responses import ApiResponse
from services.inference_service import InferenceService

router = APIRouter()


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
        data["confidence"] = data.pop("probabilities", [None])[0] if data.get("probabilities") else None
        return ApiResponse[dict[str, Any]](success=True, data=data)
    return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": result.error or "Prediction failed"})


@router.post("/train")
async def train(
    body: MlTrainRequest,
    service: InferenceService = Depends(get_inference_service),
) -> ApiResponse[MlTrainResponse]:
    symbol = body.symbols[0] if body.symbols else ""
    result = await service.train(body.model_type, symbol, body.start_date, body.end_date)
    if result.success and result.value:
        resp = MlTrainResponse(
            run_id=result.value.get("model_id", ""),
            experiment_name=body.experiment_name,
            model_type=body.model_type,
            status=result.value.get("status", "completed"),
            message=f"Model trained with accuracy {result.value.get('accuracy', 0)}",
        )
        return ApiResponse[MlTrainResponse](success=True, data=resp)
    return ApiResponse[MlTrainResponse](success=False, data=None, error={"message": result.error or "Training failed"})
