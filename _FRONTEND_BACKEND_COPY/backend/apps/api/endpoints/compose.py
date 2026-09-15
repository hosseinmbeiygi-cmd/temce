"""API endpoints for strategy composition and generation."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from schemas.common.responses import ApiResponse
from services.compose_service import get_compose_service

router = APIRouter()


class ComposeStartRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["فولاد"])
    start_date: str | None = None
    end_date: str | None = None
    capital: float = 1_000_000_000
    batch_size: int = 100_000
    max_batches: int = 10


@router.post("/start", summary="Start strategy composition")
async def compose_start(body: ComposeStartRequest) -> ApiResponse[dict[str, Any]]:
    """Start generating and testing strategy combinations."""
    svc = get_compose_service()
    if svc.is_running:
        return ApiResponse[dict[str, Any]](success=False, error={"message": "Generation already in progress"})

    start = date.fromisoformat(body.start_date) if body.start_date else None
    end = date.fromisoformat(body.end_date) if body.end_date else None

    import asyncio

    # Run in background
    asyncio.create_task(
        svc.start(
            symbols=body.symbols,
            start_date=start,
            end_date=end,
            capital=body.capital,
            batch_size=body.batch_size,
            max_batches=body.max_batches,
        )
    )

    return ApiResponse[dict[str, Any]](success=True, data={"message": "Generation started", "symbols": body.symbols})


@router.get("/status", summary="Get composition status")
async def compose_status() -> ApiResponse[dict[str, Any]]:
    svc = get_compose_service()
    return ApiResponse[dict[str, Any]](success=True, data=svc.progress)


@router.get("/results", summary="Get composition results")
async def compose_results(
    symbol: str | None = Query(None),
    entry_indicator: str | None = Query(None),
    exit_indicator: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse[dict[str, Any]]:
    svc = get_compose_service()
    results = svc.get_results(
        symbol=symbol, entry_indicator=entry_indicator, exit_indicator=exit_indicator, limit=limit
    )
    return ApiResponse[dict[str, Any]](success=True, data={"results": results, "total": len(results)})


@router.get("/top/{n}", summary="Get top N strategies")
async def compose_top(n: int = 10) -> ApiResponse[list[dict[str, Any]]]:
    svc = get_compose_service()
    return ApiResponse[list[dict[str, Any]]](success=True, data=svc.get_top(n))


@router.post("/stop", summary="Stop composition")
async def compose_stop() -> ApiResponse[dict[str, Any]]:
    svc = get_compose_service()
    svc.stop()
    return ApiResponse[dict[str, Any]](success=True, data={"message": "Generation stopped"})


@router.get("/export", summary="Export results as CSV")
async def compose_export():
    from fastapi.responses import Response

    svc = get_compose_service()
    csv = svc.export_csv()
    if not csv:
        return ApiResponse[dict[str, Any]](success=False, error={"message": "No results to export"})
    return Response(
        content=csv.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=strategies.csv"},
    )


@router.get("/stats", summary="Get indicator statistics")
async def compose_stats() -> ApiResponse[dict[str, Any]]:
    svc = get_compose_service()
    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "indicator_stats": svc.get_indicator_stats(),
            "pre_filter_stats": svc.pre_filter.get_stats(),
            "quality_filter_stats": svc.quality_filter.get_stats(),
        },
    )


@router.get("/indicators", summary="List all available indicators")
async def compose_indicators() -> ApiResponse[list[dict[str, Any]]]:
    from backtesting.composer.indicator_registry import list_all_indicators

    return ApiResponse[list[dict[str, Any]]](success=True, data=list_all_indicators())
