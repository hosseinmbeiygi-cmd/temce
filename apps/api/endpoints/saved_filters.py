"""Saved Filters API — CRUD for user-saved screener filters."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update

from apps.api.dependencies import get_current_user
from core.database import get_session
from core.logging import get_logger
from models.saved_filter import SavedFilter
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────


class SavedFilterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    logic: str = Field("and")
    sort_by: str = Field("smc_score")
    sort_order: str = Field("desc")
    market: str | None = None
    min_score: float = Field(0.0, ge=0.0, le=1.0)
    is_default: bool = False


class SavedFilterUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    filters: list[dict[str, Any]] | None = None
    logic: str | None = None
    sort_by: str | None = None
    sort_order: str | None = None
    market: str | None = None
    min_score: float | None = None
    is_default: bool | None = None


class SavedFilterResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    filters: list[dict[str, Any]]
    logic: str
    sort_by: str
    sort_order: str
    market: str | None = None
    min_score: float
    is_default: bool
    usage_count: int
    last_used_at: str | None = None
    created_at: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "",
    summary="List saved filters",
    description="Get all saved filters for the current user.",
)
async def list_saved_filters(
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[list[SavedFilterResponse]]:
    user_id = current_user.get("sub", "")
    if not user_id:
        return ApiResponse(success=False, data=[], error={"message": "Unauthorized"})

    async for session in get_session():
        result = await session.execute(
            select(SavedFilter)
            .where(SavedFilter.user_id == user_id)
            .order_by(SavedFilter.is_default.desc(), SavedFilter.usage_count.desc(), SavedFilter.created_at.desc())
        )
        rows = result.scalars().all()

        items = []
        for r in rows:
            try:
                filters = json.loads(r.filters_json) if r.filters_json else []
            except json.JSONDecodeError:
                filters = []
            items.append(SavedFilterResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                filters=filters,
                logic=r.logic,
                sort_by=r.sort_by,
                sort_order=r.sort_order,
                market=r.market,
                min_score=r.min_score,
                is_default=r.is_default,
                usage_count=r.usage_count,
                last_used_at=r.last_used_at.isoformat() if r.last_used_at else None,
                created_at=r.created_at.isoformat() if r.created_at else None,
            ))
        break

    return ApiResponse(success=True, data=items)


@router.post(
    "",
    summary="Create saved filter",
    description="Save a new screener filter preset.",
)
async def create_saved_filter(
    body: SavedFilterCreate,
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[SavedFilterResponse]:
    user_id = current_user.get("sub", "")
    if not user_id:
        return ApiResponse(success=False, data=None, error={"message": "Unauthorized"})

    filters_json = json.dumps(body.filters, ensure_ascii=False, default=str)

    # Use a single session to avoid TOCTOU race conditions
    async for session in get_session():
        # Check max saved filters per user (limit to 50)
        count_result = await session.execute(
            select(func.count()).where(SavedFilter.user_id == user_id)
        )
        count = count_result.scalar() or 0
        if count >= 50:
            return ApiResponse(success=False, data=None, error={"message": "Maximum 50 saved filters reached"})

        # If setting as default, unset other defaults
        if body.is_default:
            await session.execute(
                update(SavedFilter)
                .where(SavedFilter.user_id == user_id, SavedFilter.is_default)
                .values(is_default=False)
            )

        new_filter = SavedFilter(
            user_id=user_id,
            name=body.name,
            description=body.description,
            filters_json=filters_json,
            logic=body.logic,
            sort_by=body.sort_by,
            sort_order=body.sort_order,
            market=body.market,
            min_score=body.min_score,
            is_default=body.is_default,
        )
        session.add(new_filter)
        await session.commit()
        await session.refresh(new_filter)

        response = SavedFilterResponse(
            id=new_filter.id,
            name=new_filter.name,
            description=new_filter.description,
            filters=body.filters,
            logic=new_filter.logic,
            sort_by=new_filter.sort_by,
            sort_order=new_filter.sort_order,
            market=new_filter.market,
            min_score=new_filter.min_score,
            is_default=new_filter.is_default,
            usage_count=0,
            created_at=new_filter.created_at.isoformat() if new_filter.created_at else None,
        )
        break

    return ApiResponse(success=True, data=response)


@router.put(
    "/{filter_id}",
    summary="Update saved filter",
    description="Update an existing saved filter.",
)
async def update_saved_filter(
    filter_id: int,
    body: SavedFilterUpdate,
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[SavedFilterResponse]:
    user_id = current_user.get("sub", "")
    if not user_id:
        return ApiResponse(success=False, data=None, error={"message": "Unauthorized"})

    async for session in get_session():
        result = await session.execute(
            select(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.user_id == user_id)
        )
        existing = result.scalar_one_or_none()
        if not existing:
            raise HTTPException(status_code=404, detail="Filter not found")

        update_data: dict[str, Any] = {}
        if body.name is not None:
            update_data["name"] = body.name
        if body.description is not None:
            update_data["description"] = body.description
        if body.filters is not None:
            update_data["filters_json"] = json.dumps(body.filters, ensure_ascii=False, default=str)
        if body.logic is not None:
            update_data["logic"] = body.logic
        if body.sort_by is not None:
            update_data["sort_by"] = body.sort_by
        if body.sort_order is not None:
            update_data["sort_order"] = body.sort_order
        if body.market is not None:
            update_data["market"] = body.market
        if body.min_score is not None:
            update_data["min_score"] = body.min_score
        if body.is_default is not None:
            # If setting as default, unset other defaults
            if body.is_default:
                await session.execute(
                    update(SavedFilter)
                    .where(SavedFilter.user_id == user_id, SavedFilter.is_default)
                    .values(is_default=False)
                )
            update_data["is_default"] = body.is_default

        if update_data:
            update_data["updated_at"] = datetime.now(UTC).replace(tzinfo=None)
            await session.execute(
                update(SavedFilter).where(SavedFilter.id == filter_id).values(**update_data)
            )
            await session.commit()

        # Re-fetch
        result = await session.execute(select(SavedFilter).where(SavedFilter.id == filter_id))
        updated = result.scalar_one()
        try:
            filters = json.loads(updated.filters_json) if updated.filters_json else []
        except json.JSONDecodeError:
            filters = []

        response = SavedFilterResponse(
            id=updated.id,
            name=updated.name,
            description=updated.description,
            filters=filters,
            logic=updated.logic,
            sort_by=updated.sort_by,
            sort_order=updated.sort_order,
            market=updated.market,
            min_score=updated.min_score,
            is_default=updated.is_default,
            usage_count=updated.usage_count,
            last_used_at=updated.last_used_at.isoformat() if updated.last_used_at else None,
            created_at=updated.created_at.isoformat() if updated.created_at else None,
        )
        break

    return ApiResponse(success=True, data=response)


@router.post(
    "/{filter_id}/use",
    summary="Mark filter as used",
    description="Increment usage count and update last_used_at.",
)
async def use_saved_filter(
    filter_id: int,
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    user_id = current_user.get("sub", "")
    if not user_id:
        return ApiResponse(success=False, data=None, error={"message": "Unauthorized"})

    async for session in get_session():
        result = await session.execute(
            select(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.user_id == user_id)
        )
        existing = result.scalar_one_or_none()
        if not existing:
            raise HTTPException(status_code=404, detail="Filter not found")

        await session.execute(
            update(SavedFilter)
            .where(SavedFilter.id == filter_id)
            .values(
                usage_count=SavedFilter.usage_count + 1,
                last_used_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await session.commit()
        break

    return ApiResponse(success=True, data={"message": "Filter usage recorded"})


@router.delete(
    "/{filter_id}",
    summary="Delete saved filter",
    description="Delete a saved filter.",
)
async def delete_saved_filter(
    filter_id: int,
    current_user: dict = Depends(get_current_user),
) -> ApiResponse[dict[str, Any]]:
    user_id = current_user.get("sub", "")
    if not user_id:
        return ApiResponse(success=False, data=None, error={"message": "Unauthorized"})

    async for session in get_session():
        result = await session.execute(
            select(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.user_id == user_id)
        )
        existing = result.scalar_one_or_none()
        if not existing:
            raise HTTPException(status_code=404, detail="Filter not found")

        await session.execute(delete(SavedFilter).where(SavedFilter.id == filter_id))
        await session.commit()
        break

    return ApiResponse(success=True, data={"message": "Filter deleted"})
