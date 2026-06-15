from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_report_service
from services.report_service import ReportService

router = APIRouter()


@router.get("/market")
async def market_report(service: ReportService = Depends(get_report_service)):
    result = await service.generate_market_report()
    return {"success": result.success, "data": result.value}


@router.get("/symbol/{symbol}")
async def symbol_report(symbol: str, service: ReportService = Depends(get_report_service)):
    result = await service.generate_symbol_report(symbol)
    return {"success": result.success, "data": result.value}


@router.get("/backtest/{backtest_id}")
async def backtest_report(backtest_id: str, service: ReportService = Depends(get_report_service)):
    result = await service.generate_backtest_report(backtest_id)
    return {"success": result.success, "data": result.value}
