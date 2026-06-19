from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_report_service
from schemas.common.responses import ApiResponse
from services.report_service import ReportService

router = APIRouter()


@router.get("/market", summary="Market report", description="Generate a comprehensive market report")
async def market_report(
    service: ReportService = Depends(get_report_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.generate_market_report()
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/symbol/{symbol}", summary="Symbol report", description="Generate a detailed report for a specific symbol")
async def symbol_report(
    symbol: str,
    service: ReportService = Depends(get_report_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.generate_symbol_report(symbol)
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/backtest/{backtest_id}", summary="Backtest report", description="Generate a report for a completed backtest")
async def backtest_report(
    backtest_id: str,
    service: ReportService = Depends(get_report_service),
) -> ApiResponse[dict[str, Any]]:
    result = await service.generate_backtest_report(backtest_id)
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)
