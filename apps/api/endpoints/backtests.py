from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_backtest_service, get_db_session
from apps.api.endpoints.backtest_requests import (
    AdaptiveDecideRequest,
    CompareStrategiesRequest,
    RunOnAllSymbolsRequest,
    SaveCompareRequest,
    ScanIndicatorsRequest,
)
from backtesting.strategies.registry import get_strategy_registry, register_all_strategies
from core.ids import new_id
from core.logging import get_logger
from core.time import utc_now_naive
from models.compare import CompareResultModel
from schemas.api.backtest import BacktestRequest

logger = get_logger(__name__)
from apps.api.pagination import PaginatedResult as PydanticPaginatedResult
from schemas.common.responses import ApiResponse
from services.backtest_service import BacktestService

# Re-export PaginatedResult as the Pydantic version for route responses
PaginatedResult = PydanticPaginatedResult

router = APIRouter()


@router.post("/run")
async def run_backtest(
    body: BacktestRequest,
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any]]:
    # Multi-symbol: run all symbols and return combined results
    if len(body.symbols) > 1:
        result = await service.run_multi_symbol(
            name=body.name,
            symbols=body.symbols,
            strategy_type=body.strategy_type,
            strategy_params=body.strategy_params,
            start_date=body.start_date,
            end_date=body.end_date,
            capital=body.initial_capital,
            data_source=body.data_source,
            commission_pct=body.commission_pct,
            slippage_bps=body.slippage_bps,
            sizing_method=body.sizing_method,
            sizing_value=body.sizing_value,
            stop_loss_pct=body.stop_loss_pct,
            take_profit_pct=body.take_profit_pct,
            benchmark_symbol=body.benchmark_symbol,
        )
        return ApiResponse[dict[str, Any]](
            success=result.success,
            data=result.value,
            error={"message": result.error} if not result.success and result.error else None,
        )

    # Single symbol
    result = await service.run_backtest(
        name=body.name,
        symbols=body.symbols,
        strategy_type=body.strategy_type,
        strategy_params=body.strategy_params,
        start_date=body.start_date,
        end_date=body.end_date,
        capital=body.initial_capital,
        data_source=body.data_source,
        commission_pct=body.commission_pct,
        slippage_bps=body.slippage_bps,
        sizing_method=body.sizing_method,
        sizing_value=body.sizing_value,
        stop_loss_pct=body.stop_loss_pct,
        take_profit_pct=body.take_profit_pct,
        benchmark_symbol=body.benchmark_symbol,
    )
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value.model_dump() if hasattr(result.value, "model_dump") else result.value,
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
            ),
        )
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True,
        data=PaginatedResult(items=[], total=0, page=1, page_size=50),
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
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True,
        data=PaginatedResult(
            items=service.list_strategies(), total=len(service.list_strategies()), page=1, page_size=100
        ),
    )


@router.post(
    "/run-all", summary="Run backtest on all symbols", description="Run the selected strategy on all symbols at once"
)
async def run_backtest_on_all_symbols(
    body: RunOnAllSymbolsRequest,
    service: BacktestService = Depends(get_backtest_service),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    strategy_type = body.strategy_type
    strategy_params = body.strategy_params
    start_date = body.start_date
    end_date = body.end_date
    capital = body.initial_capital

    # Fetch symbols from the instruments table
    from sqlalchemy import text

    try:
        # Fetch ALL symbols including delisted/suspended for survivorship-bias-free backtesting
        # Only filter by status when user explicitly requests it (include_delisted=false)
        include_delisted = body.get("include_delisted", True)  # Default: True for unbiased testing
        status_filter = "" if include_delisted else "AND (i.status IS NULL OR i.status = 'active')"

        db_result = await session.execute(
            text(f"""
                SELECT DISTINCT i.symbol
                FROM instruments i
                WHERE i.symbol IS NOT NULL
                  AND i.symbol != ''
                  {status_filter}
                ORDER BY i.symbol ASC
            """)
        )
        db_symbols = [row[0] for row in db_result.fetchall()]
    except Exception as exc:
        logger.warning("Failed to fetch symbols from instruments table — DB may be down: %s", exc)
        db_symbols = []

    # Also try to get symbols from quotes table that have historical data
    try:
        q_result = await session.execute(
            text("""
                SELECT DISTINCT symbol
                FROM quotes
                WHERE symbol IS NOT NULL AND symbol != ''
                  AND price_close IS NOT NULL AND price_close > 0
                ORDER BY symbol ASC
            """)
        )
        quote_symbols = [row[0] for row in q_result.fetchall()]
    except Exception as exc:
        logger.warning("Failed to fetch symbols from quotes table: %s", exc)
        quote_symbols = []

    # Also try brsapi_historical_daily
    try:
        h_result = await session.execute(
            text("""
                SELECT DISTINCT symbol
                FROM brsapi_historical_daily
                WHERE symbol IS NOT NULL AND symbol != ''
                  AND price_close IS NOT NULL AND price_close > 0
                ORDER BY symbol ASC
            """)
        )
        hist_symbols = [row[0] for row in h_result.fetchall()]
    except Exception as exc:
        logger.warning("Failed to fetch symbols from brsapi_historical_daily table: %s", exc)
        hist_symbols = []

    # Merge all sources: use body.symbols if provided, otherwise merge all DB sources
    if "symbols" in body and body["symbols"]:
        symbols = body["symbols"]
    else:
        # Symbols that have historical data (prioritize these)
        symbols_with_history = list(dict.fromkeys(quote_symbols + hist_symbols))  # deduped, ordered
        all_active = list(dict.fromkeys(db_symbols + symbols_with_history))
        # Put symbols with history first, then the rest
        symbols = symbols_with_history + [s for s in all_active if s not in symbols_with_history]

    if not symbols:
        symbols = ["فولاد", "فملی", "شپنا", "وبملت", "خودرو"]

    today = date.today()
    start = start_date or date(today.year - 1, 1, 1)
    end = end_date or today

    if isinstance(start, str):
        start = datetime.fromisoformat(start).date()
    if isinstance(end, str):
        end = datetime.fromisoformat(end).date()

    # ── Parallel execution with concurrency control ──
    MAX_CONCURRENT = 10  # Max parallel backtests at once
    MAX_TIMEOUT = 600  # 10 minutes max for all backtests combined
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def _run_one(symbol: str) -> dict[str, Any]:
        """Run a single backtest and return the result dict."""
        async with semaphore:
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
                    "symbol": symbol,
                    "run_id": run_id,
                    "status": run_dict.get("status", "completed"),
                    "metrics": metrics,
                }
            else:
                return {
                    "symbol": symbol,
                    "status": "failed",
                    "error": result.error,
                }

    # Run all symbols in parallel (limited by semaphore + timeout)
    all_tasks = [_run_one(sym) for sym in symbols]
    try:
        results = await asyncio.wait_for(asyncio.gather(*all_tasks), timeout=MAX_TIMEOUT)
    except TimeoutError:
        logger.warning("run-all timed out after %ds for %d symbols", MAX_TIMEOUT, len(symbols))
        results = [{"symbol": s, "status": "failed", "error": "TIMEOUT"} for s in symbols]

    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "strategy_type": strategy_type,
            "total_symbols": len(symbols),
            "successful": sum(1 for r in results if r["status"] != "failed"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "results": results,
        },
    )


@router.post("/compare/save", summary="Save compare result to history")
async def save_compare_result(
    body: SaveCompareRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    compare_id = new_id("cmp")
    results_json = json.dumps(body.results, ensure_ascii=False)
    orm = CompareResultModel(
        id=compare_id,
        symbol=body.symbol,
        total_strategies=body.total_strategies,
        successful=body.successful,
        failed=body.failed,
        best=body.best,
        worst=body.worst,
        results_json=results_json,
        best_return_pct=body.best_return_pct,
        worst_return_pct=body.worst_return_pct,
        avg_return_pct=body.avg_return_pct,
        start_date=body.start_date,
        end_date=body.end_date,
        capital=body.capital,
        notes=body.get("notes", ""),
        executed_at=utc_now_naive(),
    )
    session.add(orm)
    await session.commit()
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
        items.append(
            {
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
            }
        )
    return ApiResponse[PaginatedResult[dict[str, Any]]](
        success=True,
        data=PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
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
            logger.warning("Failed to parse results_json for compare %s", compare_id)
            pass
    return ApiResponse[dict[str, Any] | None](
        success=True,
        data={
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
        },
    )


@router.post(
    "/compare",
    summary="Compare all strategies",
    description="Run all strategies on a single symbol and compare performance",
)
async def compare_strategies(
    body: CompareStrategiesRequest,
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any]]:
    symbol = body.symbol
    start_date = body.start_date
    end_date = body.end_date
    capital = body.initial_capital

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
    completed = [
        r for r in results if r["status"] != "failed" and r.get("metrics", {}).get("total_return_pct") is not None
    ]
    best = max(completed, key=lambda r: r["metrics"]["total_return_pct"]) if completed else None
    worst = min(completed, key=lambda r: r["metrics"]["total_return_pct"]) if completed else None

    # Compute Deflated Sharpe Ratio for all strategies
    try:
        from backtesting.metrics.deflated_sharpe import deflated_sharpe_ratio

        n_trials = len(completed)
        for r in completed:
            sharpe = r["metrics"].get("sharpe_ratio", 0) or 0
            n_obs = r["metrics"].get("total_trades", 30) * 20  # Approximate observations
            dsr_result = deflated_sharpe_ratio(
                sharpe_observed=sharpe,
                n_trials=max(n_trials, 1),
                n_observations=max(n_obs, 30),
            )
            r["deflated_sharpe"] = dsr_result
            r["metrics"]["deflated_sharpe"] = dsr_result.get("deflated_sharpe", 0)
            r["metrics"]["dsr_p_value"] = dsr_result.get("p_value", 1)
            r["metrics"]["dsr_significant_95"] = dsr_result.get("significant_95", False)
    except Exception as dsr_err:
        logger.warning("Deflated Sharpe computation failed: %s", dsr_err)

    # Re-rank by Deflated Sharpe (if available), otherwise by raw Sharpe
    dsr_best = None
    dsr_worst = None
    if completed:

        def _rank_key(r):
            dsr = r.get("deflated_sharpe", {}).get("deflated_sharpe", 0)
            sharpe = r["metrics"].get("sharpe_ratio", 0) or 0
            return dsr if dsr > 0 else sharpe

        dsr_best = max(completed, key=_rank_key)
        dsr_worst = min(completed, key=_rank_key)

    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "symbol": symbol,
            "total_strategies": len(strategy_names),
            "successful": sum(1 for r in results if r["status"] != "failed"),
            "failed": sum(1 for r in results if r["status"] == "failed"),
            "best": best["strategy"] if best else None,
            "worst": worst["strategy"] if worst else None,
            "dsr_best": dsr_best["strategy"] if dsr_best else None,
            "dsr_worst": dsr_worst["strategy"] if dsr_worst else None,
            "dsr_note": f"Deflated Sharpe-adjusted ranking: best={dsr_best['strategy'] if dsr_best else 'N/A'}, worst={dsr_worst['strategy'] if dsr_worst else 'N/A'}",
            "multiple_testing_note": f"Rankings adjusted for {len(completed)} strategies tested (Deflated Sharpe Ratio)",
            "results": results,
        },
    )


# ── Strategy Auto-Generator ────────────────────────────────────────────────────────────────────────────────────────────────────────

from pydantic import BaseModel, Field

from services.strategy_generator import DEFAULT_FILTERS, get_strategy_generator


class GenerateRequest(BaseModel):
    symbol: str = "فولاد"
    symbols: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    capital: float = 1_000_000_000
    max_combinations: int = 5000
    use_genetic: bool = True
    genetic_generations: int = 8
    filters: dict[str, Any] | None = None


@router.post("/generate", summary="Auto-generate and filter strategies")
async def generate_strategies(body: GenerateRequest) -> ApiResponse[dict[str, Any]]:
    """Generate thousands of strategy combinations with grid search + genetic optimization."""
    gen = get_strategy_generator()
    if gen.is_running:
        return ApiResponse[dict[str, Any]](success=False, error={"message": "Strategy generation already in progress"})

    start = date.fromisoformat(body.start_date) if body.start_date else None
    end = date.fromisoformat(body.end_date) if body.end_date else None
    symbols = body.symbols or [body.symbol]
    filters = body.filters or DEFAULT_FILTERS

    result = await gen.generate(
        symbols=symbols,
        start_date=start,
        end_date=end,
        capital=body.capital,
        max_combinations=body.max_combinations,
        use_genetic=body.use_genetic,
        genetic_generations=body.genetic_generations,
        filters=filters,
    )
    if not result.success:
        return ApiResponse[dict[str, Any]](success=False, error={"message": result.error})
    return ApiResponse[dict[str, Any]](success=True, data=result.value)


@router.get("/generate/status", summary="Strategy generation status")
async def generate_status() -> ApiResponse[dict[str, Any]]:
    """Check progress of running strategy generation."""
    gen = get_strategy_generator()
    return ApiResponse[dict[str, Any]](success=True, data=gen.progress)


@router.get("/generate/results", summary="Strategy generation results")
async def generate_results() -> ApiResponse[dict[str, Any]]:
    """Get results of last strategy generation."""
    gen = get_strategy_generator()
    return ApiResponse[dict[str, Any]](success=True, data=gen.get_results())


@router.get("/generate/history", summary="Generation history")
async def generate_history() -> ApiResponse[list[dict[str, Any]]]:
    """Get history of all strategy generation runs."""
    gen = get_strategy_generator()
    return ApiResponse[list[dict[str, Any]]](success=True, data=gen.get_history())


@router.get("/generate/export", summary="Export results as CSV")
async def generate_export():
    """Export strategy generation results as CSV file."""
    from fastapi.responses import Response

    gen = get_strategy_generator()
    csv = gen.export_csv()
    if not csv:
        return ApiResponse[dict[str, Any]](success=False, error={"message": "No results to export"})
    return Response(
        content=csv.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=strategies.csv"},
    )


class SaveStrategyRequest(BaseModel):
    strategies: list[dict[str, Any]]
    batch_name: str | None = None


@router.post("/generate/save", summary="Save selected strategies to database")
async def save_strategies(body: SaveStrategyRequest) -> ApiResponse[dict[str, Any]]:
    """Save selected strategies from generation results to the database."""
    from models.generated_strategy import GeneratedStrategyModel, GenerationBatchModel

    session_factory = None
    try:
        from core.database import async_session_factory as sf

        session_factory = sf
    except ImportError:
        logger.warning("Database import failed — saving strategies unavailable")

    if session_factory is None:
        return ApiResponse[dict[str, Any]](success=False, error={"message": "Database not available"})

    batch_id = new_id()
    saved_count = 0

    async with session_factory() as session:
        # Save batch info
        batch = GenerationBatchModel(
            id=batch_id,
            symbols=json.dumps([s.get("symbol", "") for s in body.strategies], ensure_ascii=False),
            total_configs=len(body.strategies),
            passed_filter=len(body.strategies),
            saved_to_db=0,
            status="completed",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.add(batch)

        for strat in body.strategies:
            metrics = strat.get("metrics", {})
            orm = GeneratedStrategyModel(
                id=new_id(),
                symbol=strat.get("symbol", ""),
                entry_indicator=strat.get("strategy", ""),
                entry_params=json.dumps(strat.get("params", {}), ensure_ascii=False),
                exit_indicator=strat.get("exit_indicator"),
                stop_loss_pct=strat.get("stop_loss_pct"),
                take_profit_pct=strat.get("take_profit_pct"),
                trailing_stop=str(strat.get("trailing_stop", False)),
                total_return_pct=metrics.get("total_return_pct"),
                annualized_return_pct=metrics.get("annualized_return_pct"),
                sharpe_ratio=metrics.get("sharpe_ratio"),
                sortino_ratio=metrics.get("sortino_ratio"),
                calmar_ratio=metrics.get("calmar_ratio"),
                max_drawdown_pct=metrics.get("max_drawdown_pct"),
                win_rate=metrics.get("win_rate"),
                profit_factor=metrics.get("profit_factor"),
                total_trades=metrics.get("total_trades"),
                winning_trades=metrics.get("winning_trades"),
                losing_trades=metrics.get("losing_trades"),
                score=strat.get("score", 0),
                strategy_type=strat.get("method", "generated"),
                batch_id=batch_id,
                status="active",
            )
            session.add(orm)
            saved_count += 1

        batch.saved_to_db = saved_count
        await session.commit()

    return ApiResponse[dict[str, Any]](success=True, data={"saved": saved_count, "batch_id": batch_id})


@router.get("/generate/saved", summary="Get saved strategies")
async def get_saved_strategies(
    symbol: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse[dict[str, Any]]:
    """Get previously saved strategies from database."""
    from models.generated_strategy import GeneratedStrategyModel

    try:
        from core.database import async_session_factory
    except ImportError:
        logger.warning("Database import failed — saved strategies unavailable")
        async_session_factory = None

    if async_session_factory is None:
        return ApiResponse[dict[str, Any]](success=True, data={"strategies": [], "total": 0})

    async with async_session_factory() as session:
        stmt = select(GeneratedStrategyModel).where(GeneratedStrategyModel.status == "active")
        if symbol:
            stmt = stmt.where(GeneratedStrategyModel.symbol == symbol)
        stmt = stmt.order_by(desc(GeneratedStrategyModel.score)).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()

        strategies = []
        for r in rows:
            strategies.append(
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "strategy": r.entry_indicator,
                    "params": json.loads(r.entry_params) if r.entry_params else {},
                    "metrics": {
                        "total_return_pct": r.total_return_pct,
                        "annualized_return_pct": r.annualized_return_pct,
                        "sharpe_ratio": r.sharpe_ratio,
                        "sortino_ratio": r.sortino_ratio,
                        "calmar_ratio": r.calmar_ratio,
                        "max_drawdown_pct": r.max_drawdown_pct,
                        "win_rate": r.win_rate,
                        "profit_factor": r.profit_factor,
                        "total_trades": r.total_trades,
                        "winning_trades": r.winning_trades,
                        "losing_trades": r.losing_trades,
                    },
                    "score": r.score,
                    "batch_id": r.batch_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
            )

    return ApiResponse[dict[str, Any]](success=True, data={"strategies": strategies, "total": len(strategies)})


# ── All-Indicators Full Scan (Phase 2: 30 indicators via SignalStrategy) ──────────────────────────────────────────────────────────────────


@router.post("/scan-indicators", summary="Scan all 30 indicators with 6-stage filter")
async def scan_indicators(
    body: ScanIndicatorsRequest,
) -> ApiResponse[dict[str, Any]]:
    """Run all 30 indicators via SignalStrategy with 6-stage filter across symbols.
    Returns results immediately (fire-and-forget). Poll /backtests/scan-indicators/status for progress."""
    from services.mass_scanner_service import get_mass_scanner

    scanner = get_mass_scanner()
    if scanner.is_running:
        return ApiResponse[dict[str, Any]](success=False, error={"message": "Scan already in progress"})

    symbols = body.symbols
    indicator_ids = body.indicator_ids
    filters = body.filters
    start_date = body.start_date
    end_date = body.end_date
    capital = body.capital
    batch_size = body.get("batch_size", 10)
    max_concurrent = body.get("max_concurrent", 10)

    asyncio.create_task(
        scanner.scan_all(
            symbols=symbols,
            indicator_ids=indicator_ids,
            filters=filters,
            start_date=date.fromisoformat(start_date) if start_date else None,
            end_date=date.fromisoformat(end_date) if end_date else None,
            capital=capital,
            batch_size=batch_size,
            max_concurrent=max_concurrent,
        )
    )

    return ApiResponse[dict[str, Any]](
        success=True, data={"message": "Indicator scan started", "batch_id": scanner._batch_id}
    )


@router.get("/scan-indicators/status", summary="Indicator scan status")
async def scan_indicators_status() -> ApiResponse[dict[str, Any]]:
    """Check progress of running indicator scan."""
    from services.mass_scanner_service import get_mass_scanner

    scanner = get_mass_scanner()
    return ApiResponse[dict[str, Any]](success=True, data=scanner.progress)


@router.get("/scan-indicators/results", summary="Indicator scan results")
async def scan_indicators_results(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get results from the last indicator scan from the database."""
    from sqlalchemy import text

    result = await session.execute(
        text("""
        SELECT id, symbol, entry_indicator, entry_params, exit_condition,
               total_return_pct, sharpe_ratio, max_drawdown_pct, win_rate,
               profit_factor, total_trades, score, batch_id
        FROM generated_strategies
        WHERE strategy_type = 'indicator'
        ORDER BY score DESC LIMIT 200
    """)
    )
    rows = result.fetchall()
    items = []
    for row in rows:
        items.append(
            {
                "id": row[0],
                "symbol": row[1],
                "indicator": row[2],
                "params": row[3],
                "exit_condition": row[4],
                "total_return_pct": row[5],
                "sharpe_ratio": row[6],
                "max_drawdown_pct": row[7],
                "win_rate": row[8],
                "profit_factor": row[9],
                "total_trades": row[10],
                "score": row[11],
                "batch_id": row[12],
            }
        )
    return ApiResponse[dict[str, Any]](success=True, data={"results": items, "total": len(items)})


@router.get("/data/stats", summary="Backtest data statistics")
async def data_stats(
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any]]:
    """Get statistics about available backtest data (historical, intraday, quotes)."""
    stats = await service.get_data_stats()
    return ApiResponse[dict[str, Any]](success=True, data=stats)


@router.get("/data/symbols", summary="Available symbols for backtesting")
async def data_symbols(
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Get list of symbols with available historical data."""
    symbols = await service.get_available_symbols()
    return ApiResponse[list[dict[str, Any]]](success=True, data=symbols)


# ── Walk-Forward Optimization ──────────────────────────────────────────────────────────────────────────────────────────────────────


class WalkForwardRequest(BaseModel):
    symbol: str = "فولاد"
    strategy: str = "moving_average_cross"
    start_date: str | None = None
    end_date: str | None = None
    capital: float = 1_000_000_000
    windows: int = 5
    train_ratio: float = 0.7
    max_workers: int | None = None


@router.post("/walk-forward", summary="Walk-forward optimization")
async def walk_forward(
    body: WalkForwardRequest,
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any]]:
    """Run walk-forward optimization to prevent overfitting."""
    from backtesting.optimization.walk_forward import WalkForwardOptimizer
    from services.strategy_generator import STRATEGY_PARAM_RANGES

    today = date.today()
    start = date.fromisoformat(body.start_date) if body.start_date else date(today.year - 2, 1, 1)
    end = date.fromisoformat(body.end_date) if body.end_date else today

    data = await service._load_historical_data(body.symbol, start, end)
    if not data:
        return ApiResponse[dict[str, Any]](
            success=False, error={"message": f"No historical data found for {body.symbol}"}
        )

    param_grid = STRATEGY_PARAM_RANGES.get(body.strategy, {})
    if not param_grid:
        return ApiResponse[dict[str, Any]](success=False, error={"message": f"No params for strategy {body.strategy}"})

    optimizer = WalkForwardOptimizer(windows=body.windows, train_ratio=body.train_ratio, max_workers=body.max_workers)
    result = await optimizer.optimize(
        strategy_name=body.strategy,
        param_grid=param_grid,
        data=data,
        capital=body.capital,
        simulator=service.simulator,
    )

    if "error" in result:
        return ApiResponse[dict[str, Any]](success=False, error={"message": result["error"]})
    return ApiResponse[dict[str, Any]](success=True, data=result)


# ── Monte Carlo Simulation ────────────────────────────────────────────────────────────────────────────────────────────────────────


class MonteCarloRequest(BaseModel):
    symbol: str = "فولاد"
    strategy: str = "moving_average_cross"
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    start_date: str | None = None
    end_date: str | None = None
    capital: float = 1_000_000_000
    n_simulations: int = 1000
    max_workers: int | None = None


@router.post("/monte-carlo", summary="Monte Carlo simulation")
async def monte_carlo(
    body: MonteCarloRequest,
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any]]:
    """Run Monte Carlo simulation for confidence intervals."""
    from backtesting.optimization.monte_carlo import MonteCarloSimulator

    today = date.today()
    start = date.fromisoformat(body.start_date) if body.start_date else date(today.year - 2, 1, 1)
    end = date.fromisoformat(body.end_date) if body.end_date else today

    # First run the backtest to get trades
    from backtesting.strategies.registry import get_strategy_registry, register_all_strategies

    registry = get_strategy_registry()
    if not registry.list_names():
        register_all_strategies()
    cls = registry.get(body.strategy)
    if not cls:
        return ApiResponse[dict[str, Any]](success=False, error={"message": f"Strategy {body.strategy} not found"})

    data = await service._load_historical_data(body.symbol, start, end)
    if not data:
        return ApiResponse[dict[str, Any]](
            success=False, error={"message": f"No historical data found for {body.symbol}"}
        )

    clean_params = {}
    for k, v in body.strategy_params.items():
        if isinstance(v, float) and v == int(v):
            clean_params[k] = int(v)
        else:
            clean_params[k] = v

    strategy = cls(**clean_params)
    result = service.simulator.run(strategy, initial_capital=body.capital, data=data)
    if not result.success:
        return ApiResponse[dict[str, Any]](success=False, error={"message": result.error})

    trades = [{"pnl": getattr(t, "pnl", 0), "side": str(getattr(t, "side", ""))} for t in result.value.trades]

    mc = MonteCarloSimulator(n_simulations=body.n_simulations, max_workers=body.max_workers)
    mc_result = mc.simulate(trades=trades, initial_capital=body.capital)

    if "error" in mc_result:
        return ApiResponse[dict[str, Any]](success=False, error={"message": mc_result["error"]})
    return ApiResponse[dict[str, Any]](success=True, data=mc_result)


# ── Portfolio-Level Backtest ────────────────────────────────────────────────────────────────────────────────────────────────────────


class PortfolioRunRequest(BaseModel):
    name: str = "Portfolio Backtest"
    symbols: list[str]
    strategy_type: str = "moving_average_cross"
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    start_date: str | None = None
    end_date: str | None = None
    capital: float = 1_000_000_000
    allocation_method: str = "equal"  # equal, weighted
    target_weights: dict[str, float] | None = None
    rebalance_frequency_days: int | None = None
    sizing_method: str = "fixed"
    sizing_value: float = 1000.0
    commission_pct: float | None = None
    slippage_bps: float | None = None


@router.post("/portfolio-run", summary="Run portfolio-level backtest on multiple symbols")
async def portfolio_run(
    body: PortfolioRunRequest,
    service: BacktestService = Depends(get_backtest_service),
) -> ApiResponse[dict[str, Any]]:
    """Run a multi-instrument portfolio backtest with allocation and optional rebalancing."""
    from backtesting.engine.broker import Broker
    from backtesting.engine.portfolio_simulator import PortfolioBacktestSimulator
    from backtesting.portfolio.allocator import Allocator
    from backtesting.portfolio.rebalancer import Rebalancer, RebalanceRule
    from backtesting.strategies.registry import get_strategy_registry, register_all_strategies

    registry = get_strategy_registry()
    if not registry.list_names():
        register_all_strategies()
    cls = registry.get(body.strategy_type)
    if not cls:
        return ApiResponse[dict[str, Any]](success=False, error={"message": f"Strategy {body.strategy_type} not found"})

    today = date.today()
    start = date.fromisoformat(body.start_date) if body.start_date else date(today.year - 2, 1, 1)
    end = date.fromisoformat(body.end_date) if body.end_date else today

    # Load data for all symbols
    data_by_instrument: dict[str, list[dict[str, Any]]] = {}
    for symbol in body.symbols:
        data = await service._load_historical_data(symbol, start, end)
        if data:
            data_by_instrument[symbol] = data

    if not data_by_instrument:
        return ApiResponse[dict[str, Any]](success=False, error={"message": "No data found for any symbol"})

    # Build simulator
    broker_kwargs = {}
    if body.commission_pct is not None:
        broker_kwargs["commission_pct"] = body.commission_pct
    if body.slippage_bps is not None:
        broker_kwargs["slippage_bps"] = body.slippage_bps

    allocator = Allocator(method=body.allocation_method)
    rebalancer = (
        Rebalancer(RebalanceRule(frequency_days=body.rebalance_frequency_days))
        if body.rebalance_frequency_days
        else None
    )

    simulator = PortfolioBacktestSimulator(
        broker=Broker(**broker_kwargs),
        allocator=allocator,
        rebalancer=rebalancer,
    )

    # Create strategy (use first symbol as reference for instrument_id)
    clean_params = {}
    for k, v in body.strategy_params.items():
        if isinstance(v, float) and v == int(v):
            clean_params[k] = int(v)
        else:
            clean_params[k] = v

    strategy = cls(
        instrument_id=body.symbols[0],
        sizing_method=body.sizing_method,
        sizing_value=body.sizing_value,
        **clean_params,
    )

    result = await simulator.run(
        strategy=strategy,
        initial_capital=body.capital,
        data_by_instrument=data_by_instrument,
        target_weights=body.target_weights,
    )

    if not result.success:
        return ApiResponse[dict[str, Any]](success=False, error={"message": result.error})

    bt_result = result.value
    equity_curve = [
        {"timestamp": str(ep.timestamp), "nav": ep.nav, "cash": ep.cash, "positions_value": ep.positions_value}
        for ep in bt_result.equity_curve
    ]

    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "name": body.name,
            "instruments": body.symbols,
            "total_return_pct": round(bt_result.total_return_pct, 2),
            "final_capital": bt_result.final_capital,
            "total_trades": bt_result.total_trades,
            "equity_curve": equity_curve,
            "allocation_method": body.allocation_method,
        },
    )


# ── Cascade Engine Endpoints ──────────────────────────────────────────────────────────────────────────────────────────────────────────


class CascadeRequest(BaseModel):
    symbols: list[str]
    strategies: list[str] | None = None
    features: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    capital: float = 1_000_000_000
    filters: dict[str, Any] | None = None
    use_genetic: bool = True
    genetic_generations: int = 12
    population_size: int = 50
    use_walk_forward: bool = True
    walk_forward_windows: int = 5
    walk_forward_train_ratio: float = 0.7
    stop_loss: float = 8.0
    trailing_stop: bool = True
    trailing_stop_pct: float = 5.0


@router.post("/cascade/run", summary="Run cascading filter engine")
async def cascade_run(body: CascadeRequest) -> ApiResponse[dict[str, Any]]:
    """Run the multi-stage cascading filter engine."""
    import asyncio

    from services.cascade_engine import get_cascade_engine

    engine = get_cascade_engine()
    if engine.is_running:
        return ApiResponse[dict[str, Any]](success=False, error={"message": "Engine already running"})

    start = date.fromisoformat(body.start_date) if body.start_date else None
    end = date.fromisoformat(body.end_date) if body.end_date else None

    asyncio.create_task(
        engine.run(
            symbols=body.symbols,
            strategies=body.strategies,
            features=body.features,
            start_date=start,
            end_date=end,
            capital=body.capital,
            filters=body.filters,
            use_genetic=body.use_genetic,
            genetic_generations=body.genetic_generations,
            population_size=body.population_size,
            use_walk_forward=body.use_walk_forward,
            walk_forward_windows=body.walk_forward_windows,
            walk_forward_train_ratio=body.walk_forward_train_ratio,
            stop_loss=body.stop_loss,
            trailing_stop=body.trailing_stop,
            trailing_stop_pct=body.trailing_stop_pct,
        )
    )

    return ApiResponse[dict[str, Any]](success=True, data={"message": "Cascade engine started"})


@router.get("/cascade/status", summary="Cascade engine status")
async def cascade_status() -> ApiResponse[dict[str, Any]]:
    from services.cascade_engine import get_cascade_engine

    engine = get_cascade_engine()
    return ApiResponse[dict[str, Any]](success=True, data=engine.progress)


@router.get("/cascade/results", summary="Cascade engine results")
async def cascade_results() -> ApiResponse[dict[str, Any]]:
    from services.cascade_engine import get_cascade_engine

    engine = get_cascade_engine()
    return ApiResponse[dict[str, Any]](success=True, data=engine.get_results())


@router.get("/cascade/combinations", summary="Calculate total combinations")
async def cascade_combinations(
    strategies: list[str] | None = Query(default=None),
    num_symbols: int = Query(default=1),
    use_genetic: bool = Query(default=True),
    population_size: int = Query(default=50),
    generations: int = Query(default=12),
) -> ApiResponse[dict[str, Any]]:
    from services.cascade_engine import compute_total_combinations
    from services.strategy_generator import STRATEGY_PARAM_RANGES

    total = compute_total_combinations(
        strategies=strategies or list(STRATEGY_PARAM_RANGES.keys()),
        use_genetic=use_genetic,
        population_size=population_size,
        generations=generations,
        num_symbols=num_symbols,
    )
    return ApiResponse[dict[str, Any]](success=True, data={"total": total})


# ── Adaptive Engine Endpoints ────────────────────────────────────────────────────────────────────────────────────────────────────────


@router.post("/adaptive/init", summary="Initialize adaptive trading system")
async def adaptive_init(body: CascadeRequest) -> ApiResponse[dict[str, Any]]:
    """Initialize the adaptive system with historical data."""

    from services.adaptive_engine import get_adaptive_system

    system = get_adaptive_system()
    start = date.fromisoformat(body.start_date) if body.start_date else date(2021, 1, 1)
    end = date.fromisoformat(body.end_date) if body.end_date else date.today()

    from services.backtest_service import BacktestService

    svc = BacktestService()
    all_data = []
    for sym in (body.symbols or ["فولاد"])[:5]:
        data = await svc._load_historical_data(sym, start, end)
        if data:
            all_data.extend(data)

    if not all_data:
        return ApiResponse[dict[str, Any]](
            success=False, error={"message": "No historical data found for any of the specified symbols"}
        )

    await system.initialize(all_data)

    return ApiResponse[dict[str, Any]](
        success=True, data={"message": "Adaptive system initialized", "data_points": len(all_data)}
    )


@router.post("/adaptive/decide", summary="Get adaptive trading decision")
async def adaptive_decide(body: AdaptiveDecideRequest) -> ApiResponse[dict[str, Any]]:
    """Get a trading decision from the adaptive system."""
    from services.adaptive_engine import get_adaptive_system

    system = get_adaptive_system()
    market_data = body.market_data
    portfolio_returns = body.portfolio_returns

    decision = system.decide(market_data, portfolio_returns)
    return ApiResponse[dict[str, Any]](success=True, data=decision)


@router.post("/adaptive/coevolve", summary="Run co-evolution optimization")
async def adaptive_coevolve(body: CascadeRequest) -> ApiResponse[dict[str, Any]]:
    """Run co-evolutionary optimization."""
    from services.adaptive_engine import CoEvolutionOptimizer

    start = date.fromisoformat(body.start_date) if body.start_date else date(2021, 1, 1)
    end = date.fromisoformat(body.end_date) if body.end_date else date.today()

    from services.backtest_service import BacktestService

    svc = BacktestService()
    data = await svc._load_historical_data((body.symbols or ["فولاد"])[0], start, end)
    if not data:
        return ApiResponse[dict[str, Any]](
            success=False, error={"message": f"No historical data found for {(body.symbols or ['فولاد'])[0]}"}
        )

    optimizer = CoEvolutionOptimizer(pop_size=30, generations=8)
    result = optimizer.run(data)
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.get("/adaptive/regime", summary="Get current market regime")
async def adaptive_regime() -> ApiResponse[dict[str, Any]]:
    """Get current market regime detection."""
    from services.adaptive_engine import get_adaptive_system

    system = get_adaptive_system()
    if not system.is_initialized:
        return ApiResponse[dict[str, Any]](
            success=True, data={"initialized": False, "message": "System not initialized"}
        )

    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "initialized": True,
            "current_regime": system.regime_detector.current_regime,
            "regime_label": system.regime_detector.get_regime_label(),
            "allocation": system.regime_detector.get_regime_allocation(),
            "history": system.regime_detector.regime_history[-50:],
        },
    )
