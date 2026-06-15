from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_inference_service
from services.inference_service import InferenceService

router = APIRouter()


@router.post("/predict/{model_id}")
async def predict(model_id: str, features: dict, service: InferenceService = Depends(get_inference_service)):
    result = await service.predict(model_id, features)
    return {"success": result.success, "data": result.value}
