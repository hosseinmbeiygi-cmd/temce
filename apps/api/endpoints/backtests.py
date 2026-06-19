from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_backtest_service
from schemas.api.backtest import BacktestRequest, BacktestResponse, BacktestResultResponse
from schemas.common.responses import ApiResponse
from services.backtest_service import BacktestService

router = APIRouter()


@router.post("/run")
async def run_backtest(
    body: BacktestRequest,
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[BacktestResponse]:
    result = await service.run_backtest(
        name=body.name,
        symbols=body.symbols,
        strategy_type=body.strategy_type,
        strategy_params=body.strategy_params,
        start_date=body.start_date,
        end_date=body.end_date,
        capital=body.initial_capital,
    )
    return ApiResponse[BacktestResponse](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("/runs")
async def list_backtests(
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[list[dict[str, Any]]]:
    result = await service.list_runs()
    return ApiResponse[list[dict[str, Any]]](success=True, data=result.value or [])


@router.get("/runs/{run_id}")
async def get_backtest(
    run_id: str,
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any] | None]:
    result = await service.get_run(run_id)
    return ApiResponse[dict[str, Any] | None](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("/runs/{run_id}/result")
async def get_backtest_result(
    run_id: str,
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any] | None]:
    result = await service.get_result(run_id)
    return ApiResponse[dict[str, Any] | None](
        success=result.success,
        data=result.value,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("/strategies")
async def list_strategies(
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse[list[dict[str, Any]]](success=True, data=service.list_strategies())
