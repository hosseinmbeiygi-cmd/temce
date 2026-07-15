from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_recommendation_service
from core.logging import get_logger
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.recommendation_service import RecommendationService

logger = get_logger(__name__)

router = APIRouter()


@router.post("", summary="Create recommendation", description="Create a new trading recommendation")
async def create_recommendation(
    body: dict[str, Any] = Body(...),
    service: RecommendationService = Depends(get_recommendation_service),
) -> ApiResponse[dict[str, Any]]:
    rest = {k: v for k, v in body.items() if k not in ("instrument_id", "action")}
    result = await service.create(instrument_id=body.get("instrument_id", ""), action=body.get("action", ""), **rest)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("", summary="List recommendations", description="List all trading recommendations")
async def list_recommendations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: RecommendationService = Depends(get_recommendation_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.list(page, page_size)
    return ApiResponse[PaginatedResult[dict[str, Any]]](success=result.success, data=result.value)


@router.get("/{instrument_id}", summary="Get recommendations", description="Get active recommendations for a specific instrument")
async def get_recommendations(
    instrument_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: RecommendationService = Depends(get_recommendation_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.get_active(instrument_id, page, page_size)
    return ApiResponse[PaginatedResult[dict[str, Any]]](success=result.success, data=result.value)
