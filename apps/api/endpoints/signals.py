from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_current_user, get_signal_service
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.signal_service import SignalService

router = APIRouter()


@router.get("", summary="List signals", description="List all trading signals")
async def list_all_signals(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: SignalService = Depends(get_signal_service),
) -> dict[str, Any]:
    result = await service.list(instrument_id=None, page=page, page_size=page_size)
    return {
        "success": result.success,
        "data": result.value,
        "summary": {
            "buy": 0,
            "sell": 0,
            "neutral": 0
        }
    }


@router.post("/{instrument_id}", summary="Create signal", description="Create a new trading signal for an instrument")
async def create_signal(
    instrument_id: str,
    body: dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user),
    service: SignalService = Depends(get_signal_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.create(instrument_id=instrument_id, **body)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("/{instrument_id}/latest", summary="Latest signal", description="Get the latest signal for an instrument")
async def get_latest_signal(
    instrument_id: str,
    service: SignalService = Depends(get_signal_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.get_latest(instrument_id)
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/{instrument_id}", summary="List signals by instrument", description="List signals for a specific instrument")
async def list_signals(
    instrument_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: SignalService = Depends(get_signal_service),
    ) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
        result = await service.list(instrument_id, page, page_size)
        return ApiResponse[PaginatedResult[dict[str, Any]]](success=result.success, data=result.value)
