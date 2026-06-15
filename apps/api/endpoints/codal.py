from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_codal_service
from services.codal_service import CodalService

router = APIRouter()


@router.get("")
async def list_disclosures(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1), service: CodalService = Depends(get_codal_service)
):
    result = await service.list_all(page, page_size)
    return {"success": result.success, "data": result.value}


@router.post("/{instrument_id}")
async def create_disclosure(
    instrument_id: str, body: dict[str, Any] = Body(...), service: CodalService = Depends(get_codal_service)
):
    rest = {k: v for k, v in body.items() if k not in ("title",)}
    result = await service.create(instrument_id=instrument_id, title=body.get("title", ""), **rest)
    return {"success": result.success, "data": result.value, "error": result.error if not result.success else None}


@router.get("/{instrument_id}")
async def get_disclosures(
    instrument_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: CodalService = Depends(get_codal_service),
):
    result = await service.get_by_instrument(instrument_id, page, page_size)
    return {"success": result.success, "data": result.value}
