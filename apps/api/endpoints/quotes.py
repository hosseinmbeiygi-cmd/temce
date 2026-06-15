from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_quote_service
from services.quote_service import QuoteService

router = APIRouter()


@router.post("/{instrument_id}")
async def create_quote(
    instrument_id: str, body: dict[str, Any] = Body(...), service: QuoteService = Depends(get_quote_service)
):
    result = await service.create(instrument_id=instrument_id, **body)
    return {"success": result.success, "data": result.value, "error": result.error if not result.success else None}


@router.get("/{instrument_id}/latest")
async def get_latest(instrument_id: str, service: QuoteService = Depends(get_quote_service)):
    result = await service.get_latest(instrument_id)
    return {"success": result.success, "data": result.value}


@router.get("/{instrument_id}/history")
async def get_history(
    instrument_id: str,
    start: str = Query("2024-01-01"),
    end: str = Query("2024-12-31"),
    timeframe: str = Query("1d"),
    service: QuoteService = Depends(get_quote_service),
):
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    result = await service.get_history(instrument_id, start_date, end_date, timeframe)
    return {"success": result.success, "data": result.value}
