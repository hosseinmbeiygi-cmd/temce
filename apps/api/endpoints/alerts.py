from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_current_user, get_db_session
from core.logging import get_logger
from schemas.api.alerts import AlertCreate, AlertUpdate, SignalAlertCreate
from schemas.common.responses import ApiResponse
from services.alert_service import AlertService

logger = get_logger(__name__)

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
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    svc = AlertService(session)
    result = await svc.create_alert(
        user_id=current_user["sub"],
        instrument_id=req.instrument_id,
        symbol=req.symbol,
        alert_type=req.alert_type,
        condition=req.condition,
        channels=req.channels,
        description=req.description,
        signal_id=req.signal_id,
        market=req.market,
        timeframe=req.timeframe,
    )
    if not result.success:
        return ApiResponse(success=False, error={"message": result.error})
    return ApiResponse(success=True, data=result.value)


@router.post("/from-signal")
async def create_signal_alert(
    req: SignalAlertCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """One-click: user bought/follows a signal -> subscribe to TP/SL notifications."""
    svc = AlertService(session)
    result = await svc.create_signal_alert(
        user_id=current_user["sub"],
        signal_id=req.signal_id,
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
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    svc = AlertService(session)
    result = await svc.update_alert(
        alert_id=alert_id,
        user_id=current_user["sub"],
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
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    svc = AlertService(session)
    result = await svc.delete_alert(alert_id, current_user["sub"])
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
