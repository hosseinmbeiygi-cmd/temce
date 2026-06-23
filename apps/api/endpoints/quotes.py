from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from apps.api.dependencies import get_current_user, get_quote_service
from schemas.common.responses import ApiResponse
from services.quote_service import QuoteService

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.post(
    "/{instrument_id}",
    summary="Create quote",
    description="Create a new quote for an instrument",
)
async def create_quote(
    instrument_id: str,
    body: dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user),
    service: QuoteService = Depends(get_quote_service),
) -> ApiResponse[Any]:

    result = await service.create(instrument_id=instrument_id, **body)

    return ApiResponse[Any](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get(
    "/{instrument_id}/latest",
    summary="Latest quote",
    description="Get the latest quote for an instrument",
)
async def get_latest(
    instrument_id: str,
    service: QuoteService = Depends(get_quote_service),
) -> ApiResponse[Any]:

    result = await service.get_latest(instrument_id)

    return ApiResponse[Any](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get(
    "/{instrument_id}/history",
    summary="Quote history",
    description="Get historical quotes for an instrument",
)
async def get_history(
    instrument_id: str,
    start: str = Query("2024-01-01"),
    end: str = Query("2024-12-31"),
    timeframe: str = Query("1d"),
    service: QuoteService = Depends(get_quote_service),
) -> ApiResponse[Any]:

    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return ApiResponse[Any](
            success=False,
            data=None,
            error={"message": "Invalid date format. Use YYYY-MM-DD"},
        )

    result = await service.get_history(
        instrument_id,
        start_date,
        end_date,
        timeframe,
    )

    return ApiResponse[Any](
        success=result.success,
        data=result.value if result.success else None,
        error={"message": result.error} if not result.success and result.error else None,
    )
@router.get("/test/{instrument_id}")
async def test_quote_direct(instrument_id: str):
    """
    اندپوینت تست مستقل که مستقیماً از SQLite استفاده می‌کند.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from services.quote_service import QuoteService
    
    engine = create_async_engine("sqlite+aiosqlite:///data/market.db")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        service = QuoteService(session=session)
        result = await service.get_latest(instrument_id)
        if result.success:
            return {"success": True, "price": result.value.price_close}
        return {"success": False, "error": result.error}