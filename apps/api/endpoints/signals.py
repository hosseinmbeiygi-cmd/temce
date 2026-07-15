from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_signal_service
from core.logging import get_logger
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.signal_service import SignalService

logger = get_logger(__name__)

router = APIRouter()


@router.get("", summary="List signals", description="List all trading signals")
async def list_all_signals(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: SignalService = Depends(get_signal_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    try:
        result = await service.list(instrument_id=None, page=page, page_size=page_size)
        return ApiResponse[PaginatedResult[dict[str, Any]]](success=result.success, data=result.value)
    except Exception as exc:
        logger.exception("Signal list failed")
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=0),
            error={"message": str(exc)},
        )


@router.post("/{instrument_id}", summary="Create signal", description="Create a new trading signal for an instrument")
async def create_signal(
    instrument_id: str,
    body: dict[str, Any] = Body(...),
    service: SignalService = Depends(get_signal_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        result = await service.create(instrument_id=instrument_id, **body)
        return ApiResponse[dict[str, Any]](
            success=result.success,
            data=result.value,
            error={"message": result.error} if not result.success and result.error else None,
        )
    except Exception as exc:
        logger.exception("Signal create failed for %s", instrument_id)
        return ApiResponse[dict[str, Any]](
            success=False,
            data=None,
            error={"message": str(exc)},
        )


@router.get("/{instrument_id}/latest", summary="Latest signal", description="Get the latest signal for an instrument")
async def get_latest_signal(
    instrument_id: str,
    service: SignalService = Depends(get_signal_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        result = await service.get_latest(instrument_id)
        return ApiResponse[dict[str, Any]](success=result.success, data=result.value)
    except Exception as exc:
        logger.exception("Signal get_latest failed for %s", instrument_id)
        return ApiResponse[dict[str, Any]](success=False, data=None, error={"message": str(exc)})


@router.get("/{instrument_id}", summary="List signals by instrument", description="List signals for a specific instrument")
async def list_signals(
    instrument_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: SignalService = Depends(get_signal_service),
    ) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
        try:
            result = await service.list(instrument_id, page, page_size)
            return ApiResponse[PaginatedResult[dict[str, Any]]](success=result.success, data=result.value)
        except Exception as exc:
            logger.exception("Signal list failed for %s", instrument_id)
            return ApiResponse[PaginatedResult[dict[str, Any]]](
                success=False,
                data=PaginatedResult(items=[], total=0, page=page, page_size=page_size, total_pages=0),
                error={"message": str(exc)},
            )
