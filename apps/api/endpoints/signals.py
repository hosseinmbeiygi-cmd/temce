from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_signal_service
from services.signal_service import SignalService

router = APIRouter()


@router.get("")
async def list_all_signals(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1), service: SignalService = Depends(get_signal_service)
):
    result = await service.list(instrument_id=None, page=page, page_size=page_size)
    return {"success": result.success, "data": result.value}


@router.post("/{instrument_id}")
async def create_signal(
    instrument_id: str, body: dict[str, Any] = Body(...), service: SignalService = Depends(get_signal_service)
):
    result = await service.create(instrument_id=instrument_id, **body)
    return {"success": result.success, "data": result.value, "error": result.error if not result.success else None}


@router.get("/{instrument_id}/latest")
async def get_latest_signal(instrument_id: str, service: SignalService = Depends(get_signal_service)):
    result = await service.get_latest(instrument_id)
    return {"success": result.success, "data": result.value}


@router.get("/{instrument_id}")
async def list_signals(
    instrument_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: SignalService = Depends(get_signal_service),
):
    result = await service.list(instrument_id, page, page_size)
    return {"success": result.success, "data": result.value}
