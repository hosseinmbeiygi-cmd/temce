from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_backtest_service, get_db_session
from backtesting.strategies.registry import get_strategy_registry, register_all_strategies
from core.ids import new_id
from core.result import PaginatedResult
from models.compare import CompareResultModel
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
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    result = await service.list_runs()
    if result.success and result.value:
        items = result.value
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=True,
            data=PaginatedResult(
                items=items,
                total=len(items),
                page=1,
                page_size=max(len(items), 50),
                total_pages=1,
            ),
        )
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True,
        data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0),
    )


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
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    return ApiResponse[PaginatedResult[dict[str, Any]]](success=True, data=PaginatedResult(items=service.list_strategies(), total=len(service.list_strategies()), page=1, page_size=100, total_pages=1))


@router.post("/run-all", summary="Run backtest on all symbols", description="Run the selected strategy on all symbols at once")
async def run_backtest_on_all_symbols(
    body: dict[str, Any],
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any]]:
    strategy_type = body.get("strategy_type", "moving_average_cross")
    symbols = body.get("symbols", [
        "فولاد", "فملی", "شپنا", "وبملت", "خودرو", "ذوب", "رمپنا", "اخابر",
        "شستا", "غگیلا", "پارسان", "کگل", "فخوز", "حفاری", "چادرملو",
        "وبانک", "فولاژ", "فسپا", "شبندر", "شتران", "مارون", "نوری",
        "خساپا", "خگستر", "غصینو", "قشکر", "کچاد", "ومعادن", "وتوصا",
    ])
    strategy_params = body.get("strategy_params", {})
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    capital = body.get("initial_capital", 1_000_000_000)

    today = date.today()
    start = start_date or date(today.year - 1, 1, 1)
    end = end_date or today

    if isinstance(start, str):
        start = datetime.fromisoformat(start).date()
    if isinstance(end, str):
        end = datetime.fromisoformat(end).date()

    results = []
    for symbol in symbols:
        result = await service.run_backtest(
            name=f"{strategy_type}-{symbol}",
            symbols=[symbol],
            strategy_type=strategy_type,
            strategy_params=strategy_params,
            start_date=start,
            end_date=end,
            capital=capital,
        )
        if result.success:
            run_data = result.value
            run_dict = run_data.model_dump() if hasattr(run_data, "model_dump") else vars(run_data)
            # Fetch full result from service for detailed metrics
            run_id = run_dict.get("id", "")
            full_result = await service.get_result(run_id)
            metrics = {}
            if full_result.success and full_result.value:
                r = full_result.value
                metrics = {
                    "total_return_pct": r.get("total_return_pct"),
                    "sharpe_ratio": r.get("sharpe_ratio"),
                    "win_rate": r.get("win_rate"),
                    "max_drawdown_pct": r.get("max_drawdown_pct"),
                    "total_trades": r.get("total_trades"),
                    "annualized_return_pct": r.get("annualized_return_pct"),
                }
            results.append({
                "symbol": symbol,
                "run_id": run_id,
                "status": run_dict.get("status", "completed"),
                "metrics": metrics,
            })
        else:
            results.append({
                "symbol": symbol,
                "status": "failed",
                "error": result.error,
            })

    return ApiResponse[dict[str, Any]](success=True, data={
        "strategy_type": strategy_type,
        "total_symbols": len(symbols),
        "successful": sum(1 for r in results if r["status"] != "failed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    })


@router.post("/compare/save", summary="Save compare result to history")
async def save_compare_result(
    body: dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    compare_id = new_id("cmp")
    results_json = json.dumps(body.get("results", []), ensure_ascii=False)
    orm = CompareResultModel(
        id=compare_id,
        symbol=body.get("symbol", ""),
        total_strategies=body.get("total_strategies", 0),
        successful=body.get("successful", 0),
        failed=body.get("failed", 0),
        best=body.get("best"),
        worst=body.get("worst"),
        results_json=results_json,
        best_return_pct=body.get("best_return_pct"),
        worst_return_pct=body.get("worst_return_pct"),
        avg_return_pct=body.get("avg_return_pct"),
        start_date=body.get("start_date"),
        end_date=body.get("end_date"),
        capital=body.get("capital"),
        notes=body.get("notes", ""),
        executed_at=datetime.now(),
    )
    session.add(orm)
    await session.flush()
    return ApiResponse[dict[str, Any]](success=True, data={"id": compare_id, "saved": True})


@router.get("/compare/history", summary="List compare history")
async def list_compare_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    symbol: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    from sqlalchemy import func as sa_func

    # Build base query
    base_q = select(CompareResultModel)
    if symbol:
        base_q = base_q.where(CompareResultModel.symbol == symbol)

    # Efficient count
    count_q = select(sa_func.count()).select_from(base_q.subquery())
    count_result = await session.execute(count_q)
    total = count_result.scalar() or 0

    # Paginated fetch
    offset = (page - 1) * page_size
    stmt = base_q.order_by(desc(CompareResultModel.created_at)).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "symbol": r.symbol,
            "total_strategies": r.total_strategies,
            "successful": r.successful,
            "failed": r.failed,
            "best": r.best,
            "worst": r.worst,
            "best_return_pct": r.best_return_pct,
            "worst_return_pct": r.worst_return_pct,
            "avg_return_pct": r.avg_return_pct,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True,
        data=PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=max(1, (total + page_size - 1) // page_size),
        ),
    )


@router.get("/compare/history/{compare_id}", summary="Get saved compare result details")
async def get_compare_history_detail(
    compare_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any] | None]:
    stmt = select(CompareResultModel).where(CompareResultModel.id == compare_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Compare result not found")
    results_data = []
    if row.results_json:
        try:
            results_data = json.loads(row.results_json)
        except (json.JSONDecodeError, TypeError):
            pass
    return ApiResponse[dict[str, Any] | None](success=True, data={
        "id": row.id,
        "symbol": row.symbol,
        "total_strategies": row.total_strategies,
        "successful": row.successful,
        "failed": row.failed,
        "best": row.best,
        "worst": row.worst,
        "best_return_pct": row.best_return_pct,
        "worst_return_pct": row.worst_return_pct,
        "avg_return_pct": row.avg_return_pct,
        "start_date": row.start_date,
        "end_date": row.end_date,
        "capital": row.capital,
        "notes": row.notes,
        "results": results_data,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    })


@router.post("/compare", summary="Compare all strategies", description="Run all strategies on a single symbol and compare performance")
async def compare_strategies(
    body: dict[str, Any],
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any]]:
    symbol = body.get("symbol", "فولاد")
    start_date = body.get("start_date")
    end_date = body.get("end_date")
    capital = body.get("initial_capital", 1_000_000_000)

    today = date.today()
    start = start_date or date(today.year - 1, 1, 1)
    end = end_date or today

    if isinstance(start, str):
        start = datetime.fromisoformat(start).date()
    if isinstance(end, str):
        end = datetime.fromisoformat(end).date()

    registry = get_strategy_registry()
    if not registry.list_names():
        register_all_strategies()

    strategy_names = registry.list_names()

    async def _run_strategy(strategy_name: str) -> dict[str, Any]:
        try:
            result = await service.run_backtest(
                name=f"compare-{strategy_name}-{symbol}",
                symbols=[symbol],
                strategy_type=strategy_name,
                strategy_params={},
                start_date=start,
                end_date=end,
                capital=capital,
            )
            if result.success:
                run_data = result.value
                run_dict = run_data.model_dump() if hasattr(run_data, "model_dump") else vars(run_data)
                run_id = run_dict.get("id", "")
                full_result = await service.get_result(run_id)
                metrics = {}
                if full_result.success and full_result.value:
                    r = full_result.value
                    metrics = {
                        "total_return_pct": r.get("total_return_pct"),
                        "sharpe_ratio": r.get("sharpe_ratio"),
                        "win_rate": r.get("win_rate"),
                        "max_drawdown_pct": r.get("max_drawdown_pct"),
                        "total_trades": r.get("total_trades"),
                        "annualized_return_pct": r.get("annualized_return_pct"),
                    }
                return {
                    "strategy": strategy_name,
                    "run_id": run_id,
                    "status": run_dict.get("status", "completed"),
                    "metrics": metrics,
                }
            else:
                return {
                    "strategy": strategy_name,
                    "status": "failed",
                    "error": result.error,
                }
        except Exception as e:
            return {
                "strategy": strategy_name,
                "status": "failed",
                "error": str(e),
            }

    # Run all strategies in parallel
    results = await asyncio.gather(*[_run_strategy(name) for name in strategy_names])

    # Find best/worst based on total_return_pct
    completed = [r for r in results if r["status"] != "failed" and r.get("metrics", {}).get("total_return_pct") is not None]
    best = max(completed, key=lambda r: r["metrics"]["total_return_pct"]) if completed else None
    worst = min(completed, key=lambda r: r["metrics"]["total_return_pct"]) if completed else None

    return ApiResponse[dict[str, Any]](success=True, data={
        "symbol": symbol,
        "total_strategies": len(strategy_names),
        "successful": sum(1 for r in results if r["status"] != "failed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "best": best["strategy"] if best else None,
        "worst": worst["strategy"] if worst else None,
        "results": results,
    })
