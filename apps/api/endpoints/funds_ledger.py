"""🧾 Funds Ledger API — دفتر مالی دوطرفه + حرکت واحدها (فاز ۲ معماری).

مسیرها زیر ``/funds/v2/ledger``:

  POST /funds/v2/ledger/{fund_id}/unit-movements   — ثبت حرکت واحد + سند دوطرفه
  GET  /funds/v2/ledger/{fund_id}/trial-balance    — تراز آزمایشی
  GET  /funds/v2/ledger/{fund_id}/entries          — اسناد مالی
  GET  /funds/v2/ledger/{fund_id}/unit-movements   — تاریخچه حرکت واحدها
  POST /funds/v2/ledger/entries/{entry_id}/reverse — سند برگشتی (بدون حذف)
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from core.logging import get_logger
from services.fund_ledger import FundLedgerService

logger = get_logger(__name__)
router = APIRouter()


def _canonical_fund_id(raw: str) -> str:
    if ":" in raw:
        return raw
    return f"tse:{raw}"


def _get_ledger(session: AsyncSession = Depends(get_db_session)) -> FundLedgerService:
    return FundLedgerService(session=session)


class UnitMovementRequest(BaseModel):
    movement_type: str = Field(description="ISSUE|REDEEM|DISTRIBUTION|TRANSFER|PLEDGE|RELEASE")
    movement_date: date
    units: float = Field(gt=0)
    price_per_unit: float | None = Field(default=None, ge=0)
    reference: str | None = None
    nav_type: str | None = Field(default=None, description="STATISTICAL|ISSUANCE|REDEMPTION")


class ReverseRequest(BaseModel):
    memo: str | None = None


@router.post("/{fund_id}/unit-movements", summary="ثبت حرکت واحد + سند دوطرفه")
async def record_unit_movement(
    fund_id: str,
    body: UnitMovementRequest,
    ledger: FundLedgerService = Depends(_get_ledger),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    try:
        result = await ledger.record_unit_movement(
            fund_id=fid,
            movement_type=body.movement_type,
            movement_date=body.movement_date,
            units=body.units,
            price_per_unit=body.price_per_unit,
            reference=body.reference,
            nav_type=body.nav_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "data": result.data,
        "freshness": result.freshness,
        "fetched_from": result.fetched_from,
    }


@router.get("/{fund_id}/trial-balance", summary="تراز آزمایشی دفتر")
async def get_trial_balance(
    fund_id: str,
    ledger: FundLedgerService = Depends(_get_ledger),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    data = await ledger.trial_balance(fid)
    return {"success": True, "data": data}


@router.get("/{fund_id}/entries", summary="اسناد مالی صندوق")
async def list_entries(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    ledger: FundLedgerService = Depends(_get_ledger),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    entries = await ledger.list_entries(fid, limit=limit)
    return {"success": True, "data": {"entries": entries, "total": len(entries)}}


@router.get("/{fund_id}/unit-movements", summary="تاریخچه حرکت واحدها")
async def list_unit_movements(
    fund_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    ledger: FundLedgerService = Depends(_get_ledger),
) -> dict[str, Any]:
    fid = _canonical_fund_id(fund_id)
    movements = await ledger.list_unit_movements(fid, limit=limit)
    return {"success": True, "data": {"movements": movements, "total": len(movements)}}


@router.post("/entries/{entry_id}/reverse", summary="ثبت سند برگشتی")
async def reverse_entry(
    entry_id: int,
    body: ReverseRequest | None = None,
    ledger: FundLedgerService = Depends(_get_ledger),
) -> dict[str, Any]:
    body = body or ReverseRequest()
    try:
        data = await ledger.reverse_entry(entry_id, memo=body.memo)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}
