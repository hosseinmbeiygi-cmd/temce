from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from schemas.api.alerts import AlertCreate, AlertListResponse, AlertResponse, AlertUpdate
from schemas.common.responses import ApiResponse
from services.alert_service import AlertService

router = APIRouter()


@router.get("/")
async def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse:
    svc = AlertService(session)
    result = await svc.list_alerts(page, page_size)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.post("/")
async def create_alert(
    req: AlertCreate,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse:
    svc = AlertService(session)
    result = await svc.create_alert(
        user_id="anonymous",
        instrument_id=req.instrument_id,
        symbol=req.symbol,
        alert_type=req.alert_type,
        condition=req.condition,
        channels=req.channels,
        description=req.description,
    )
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.put("/{alert_id}")
async def update_alert(
    alert_id: str,
    req: AlertUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse:
    svc = AlertService(session)
    result = await svc.update_alert(
        alert_id=alert_id,
        user_id="anonymous",
        condition=req.condition,
        channels=req.channels,
        enabled=req.enabled,
        description=req.description,
    )
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse:
    svc = AlertService(session)
    result = await svc.delete_alert(alert_id, "anonymous")
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, message="Alert deleted")


@router.get("/{alert_id}/history")
async def get_alert_history(
    alert_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse:
    svc = AlertService(session)
    result = await svc.get_alert_history(alert_id, page, page_size)
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)
