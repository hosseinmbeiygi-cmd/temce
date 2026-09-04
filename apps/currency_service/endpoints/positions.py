"""CRUD endpoints for manual positions.

Auth: minimal X-User-Id header (matches the spec's "manual" intent — replace
/// with real JWT verification when apps/api auth is wired in).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.currency_service.services.position_tracker import PositionTracker
from apps.currency_service.services.signal_engine import SignalEngine
from core.database import get_session

router = APIRouter()
_engine = SignalEngine()


class CreatePositionRequest(BaseModel):
    asset_type: str = Field(pattern="^(CASH_USD|USDT)$")
    entry_price: float = Field(gt=0)
    volume: float = Field(gt=0)
    entry_date: date | None = None
    note: str | None = Field(default=None, max_length=500)


def _require_user(x_user_id: str | None = Header(default=None)) -> str:
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header required (manual-tracker placeholder auth)",
        )
    return x_user_id.strip()


def _price_map(snap) -> dict[str, float]:
    return {
        "free_sell": float(snap.free.sell_price),
        "usdt_sell": float(snap.usdt.sell_price),
    }


@router.post("/positions", status_code=status.HTTP_201_CREATED)
async def create_position(
    body: CreatePositionRequest,
    user_id: str = Depends(_require_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    tracker = PositionTracker(session)
    pos = await tracker.create(
        user_id=user_id,
        asset_type=body.asset_type,
        entry_price=body.entry_price,
        volume=body.volume,
        entry_date=body.entry_date,
        note=body.note,
    )
    return {
        "id": pos.id,
        "user_id": pos.user_id,
        "asset_type": pos.asset_type,
        "entry_price": pos.entry_price,
        "volume": pos.volume,
        "entry_date": pos.entry_date.isoformat(),
        "created_at": pos.created_at.isoformat(),
        "note": pos.note,
    }


@router.get("/positions")
async def list_positions(
    user_id: str = Depends(_require_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    tracker = PositionTracker(session)
    positions = await tracker.list_for_user(user_id)
    snap = await _engine.snapshot()
    prices = _price_map(snap)
    rows: list[dict[str, Any]] = []
    for pos in positions:
        current = tracker.price_for(pos, prices)
        pnl = tracker.pnl_for(pos, current)
        rows.append(
            {
                "id": pos.id,
                "asset_type": pos.asset_type,
                "entry_price": pos.entry_price,
                "volume": pos.volume,
                "entry_date": pos.entry_date.isoformat(),
                "created_at": pos.created_at.isoformat(),
                "note": pos.note,
                "current_price": pnl.current_price,
                "pnl_toman": round(pnl.pnl_toman, 2),
                "return_pct": round(pnl.return_pct, 2),
            }
        )
    return {"count": len(rows), "positions": rows}


@router.delete("/positions/{position_id}")
async def delete_position(
    position_id: int,
    user_id: str = Depends(_require_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    tracker = PositionTracker(session)
    ok = await tracker.delete(position_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="position not found")
    return {"deleted": True, "id": position_id}
