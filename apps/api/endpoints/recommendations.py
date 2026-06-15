from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_recommendation_service
from services.recommendation_service import RecommendationService

router = APIRouter()


@router.post("")
async def create_recommendation(
    body: dict[str, Any] = Body(...), service: RecommendationService = Depends(get_recommendation_service)
):
    rest = {k: v for k, v in body.items() if k not in ("instrument_id", "action")}
    result = await service.create(instrument_id=body.get("instrument_id", ""), action=body.get("action", ""), **rest)
    return {"success": result.success, "data": result.value, "error": result.error if not result.success else None}


@router.get("")
async def list_recommendations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: RecommendationService = Depends(get_recommendation_service),
):
    result = await service.list(page, page_size)
    return {"success": result.success, "data": result.value}


@router.get("/{instrument_id}")
async def get_recommendations(instrument_id: str, service: RecommendationService = Depends(get_recommendation_service)):
    result = await service.get_active(instrument_id)
    return {"success": result.success, "data": result.value}
