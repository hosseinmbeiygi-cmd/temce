from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Path, Query

from apps.api.dependencies import get_brsapi_query_service, get_market_service
from core.logging import get_logger
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse
from services.market_service import MarketService

logger = get_logger(__name__)

router = APIRouter()


@router.get("/overview", summary="Market overview", description="Get overall market summary including indices and sector performance")
async def market_overview(service: MarketService = Depends(get_market_service)) -> ApiResponse[dict[str, Any]]:
    result = await service.get_overview()
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/indices", summary="Market indices", description="Get latest index values (TSE, FaraBourse, etc.)")
async def market_indices(service: MarketService = Depends(get_market_service)) -> ApiResponse[list[dict[str, Any]]]:
    result = await service.get_index_values()
    return ApiResponse[list[dict[str, Any]]](success=result.success, data=result.value)


@router.get("/gainers", summary="Top gainers", description="Get top gaining symbols")
async def top_gainers(
    limit: int = Query(10, ge=1, le=100),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[Any]:
    result = await service.get_top_gainers(limit)
    return ApiResponse[Any](success=result.success, data=result.value)


@router.get("/losers", summary="Top losers", description="Get top losing symbols")
async def top_losers(
    limit: int = Query(10, ge=1, le=100),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[Any]:
    result = await service.get_top_losers(limit)
    return ApiResponse[Any](success=result.success, data=result.value)


@router.get("/active", summary="Most active", description="Get most actively traded symbols")
async def most_active(
    limit: int = Query(10, ge=1, le=100),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[Any]:
    result = await service.get_most_active(limit)
    return ApiResponse[Any](success=result.success, data=result.value)


@router.get("/watch", summary="Market watch", description="Get market watch list")
async def market_watch(service: MarketService = Depends(get_market_service)) -> ApiResponse[PaginatedResult[Any]]:
    result = await service.get_market_watch()
    if not result.success:
        return ApiResponse[PaginatedResult[Any]](success=False, data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1))

    items = result.value
    return ApiResponse[PaginatedResult[Any]](
        success=True,
        data=PaginatedResult(
            items=items,
            total=len(items),
            page=1,
            page_size=len(items),
            total_pages=1,
        )
    )


@router.get("/bourse", summary="Bourse instruments", description="List instruments in the Bourse market")
async def get_bourse(service: MarketService = Depends(get_market_service)) -> ApiResponse[PaginatedResult[Any]]:
    result = await service.get_instruments_by_market("BOURS")
    if not result.success:
        return ApiResponse[PaginatedResult[Any]](success=False, data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1))
    items = result.value
    items.sort(key=lambda x: x.symbol or "")
    return ApiResponse[PaginatedResult[Any]](
        success=True,
        data=PaginatedResult(
            items=[vars(i) for i in items],
            total=len(items),
            page=1,
            page_size=len(items),
            total_pages=1,
        )
    )


@router.get("/energy-commodity", summary="Energy & Commodity", description="List energy and commodity instruments")
async def get_energy_commodity(service: MarketService = Depends(get_market_service)) -> ApiResponse[dict[str, Any]]:
    result = await service.get_energy_commodity_summary()
    return ApiResponse[dict[str, Any]](success=result.success, data=result.value)


@router.get("/heatmap", summary="Market heatmap", description="Symbol heatmap data for visualisation")
async def market_heatmap(
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        snapshots = await brsapi.get_latest_snapshots(limit=100)
        cells = [
            {
                "symbol": s.get("symbol", ""),
                "name": s.get("name", ""),
                "change": s.get("price_last_change_pct", 0) or 0,
                "value": s.get("trade_value", 0) or 0,
                "volume": s.get("trade_volume", 0) or 0,
                "price": s.get("price_last", 0) or 0,
            }
            for s in snapshots if s.get("symbol")
        ]
        cells.sort(key=lambda x: abs(x["change"]), reverse=True)
        return ApiResponse[list[dict[str, Any]]](success=True, data=cells)
    except Exception as exc:
        logger.exception("Market heatmap failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/indicator/{symbol}",
    summary="Technical indicator",
    description="Compute a technical indicator for a symbol (sma, ema, rsi, macd, bollinger, stochastic, atr, obv, williams_r, ichimoku)",
)
async def market_indicator(
    symbol: str = Path(..., description="Symbol name (e.g. فولاد, IRO1FOLD0001)"),
    indicator: str = Query(..., description="Indicator: sma, ema, rsi, macd, bollinger, stochastic, atr, obv, williams_r, ichimoku"),
    period: int = Query(14, ge=1, le=500, description="Lookback period"),
    fast: int = Query(12, ge=1, le=500, description="Fast period (MACD)"),
    slow: int = Query(26, ge=1, le=500, description="Slow period (MACD)"),
    signal: int = Query(9, ge=1, le=500, description="Signal period (MACD)"),
    k_smooth: int = Query(3, ge=1, le=50, description="%K smoothing (Stochastic)"),
    d_smooth: int = Query(3, ge=1, le=50, description="%D smoothing (Stochastic)"),
    stddev: float = Query(2.0, ge=0.1, le=10.0, description="Standard deviation multiplier (Bollinger)"),
    tenkan: int = Query(9, ge=1, le=200, description="Tenkan-sen period (Ichimoku)"),
    kijun: int = Query(26, ge=1, le=200, description="Kijun-sen period (Ichimoku)"),
    senkou_b: int = Query(52, ge=1, le=200, description="Senkou Span B period (Ichimoku)"),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[dict[str, Any]]:
    params: dict[str, Any] = {
        "period": period,
        "fast": fast,
        "slow": slow,
        "signal": signal,
        "k_smooth": k_smooth,
        "d_smooth": d_smooth,
        "stddev": stddev,
        "tenkan": tenkan,
        "kijun": kijun,
        "senkou_b": senkou_b,
    }
    result = await service.calculate_indicator(symbol, indicator, params)
    return ApiResponse[dict[str, Any]](
        success=result.success,
        data=result.value if result.success else {},
        error={"message": result.error} if result.error else None,
    )


@router.get(
    "/history/{symbol}",
    summary="Historical OHLCV",
    description="Get historical OHLCV data for candlestick charts",
)
async def market_history(
    symbol: str = Path(..., description="Symbol name"),
    limit: int = Query(200, ge=1, le=500, description="Number of bars to return"),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[list[dict[str, Any]]]:
    from datetime import date, timedelta
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=limit * 3)).isoformat()
    result = await service.get_ohlcv(symbol, start, end)
    return ApiResponse[list[dict[str, Any]]](
        success=result.success,
        data=result.value if result.success else [],
        error={"message": result.error} if result.error else None,
    )


@router.get(
    "/sparklines",
    summary="Batch sparkline data",
    description="Get last N close prices for multiple symbols in one call (for mini-charts on list pages)",
)
async def market_sparklines(
    symbols: str = Query(..., description="Comma-separated symbol names, e.g. فولاد,فملی,خودرو"),
    limit: int = Query(30, ge=5, le=200, description="Number of close prices per symbol"),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[dict[str, list[float]]]:
    try:
        sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
        result = await service.get_batch_sparklines(sym_list, limit)
        return ApiResponse[dict[str, list[float]]](
            success=True,
            data=result.value if result.success else {},
        )
    except Exception as exc:
        logger.exception("Market sparklines failed")
        return ApiResponse[dict[str, list[float]]](
            success=False,
            data={},
            error={"message": str(exc)},
        )


@router.get("/enriched-heatmap", summary="Enriched market heatmap", description="Symbol heatmap data enriched with price thresholds, free float, sector info")
async def market_enriched_heatmap(
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        enriched = await brsapi.get_enriched_snapshots(limit=500)
        cells = [
            {
                "symbol": s.get("symbol", ""),
                "name": s.get("name", ""),
                "change": s.get("price_last_change_pct", 0) or 0,
                "value": s.get("trade_value", 0) or 0,
                "volume": s.get("trade_volume", 0) or 0,
                "price": s.get("price_last", 0) or 0,
                "priceLowestAllowed": s.get("price_lowest_allowed", 0) or 0,
                "priceHighestAllowed": s.get("price_highest_allowed", 0) or 0,
                "freeFloatPct": s.get("free_float_pct", 0) or 0,
                "eps": s.get("eps", 0) or 0,
                "peRatio": s.get("pe_ratio", 0) or 0,
                "state": s.get("state", ""),
                "sector": s.get("sector", ""),
                "market": s.get("market", ""),
                "board": s.get("board", ""),
            }
            for s in enriched if s.get("symbol")
        ]
        return ApiResponse[list[dict[str, Any]]](success=True, data=cells)
    except Exception as exc:
        logger.exception("Enriched heatmap failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get("/treemap", summary="Market treemap", description="Hierarchical treemap data grouped by sector for visualization")
async def market_treemap(
    limit: int = Query(2000, ge=50, le=5000),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[dict[str, Any]]:
    """Return symbols grouped by sector for treemap visualization."""
    try:
        from collections import defaultdict

        enriched = await brsapi.get_enriched_snapshots(limit=limit)

        # Group by sector
        sectors: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for s in enriched:
            symbol = s.get("symbol", "")
            if not symbol:
                continue
            sector = s.get("sector", "سایر")
            trade_value = s.get("trade_value", 0) or 0

            sectors[sector].append({
                "name": symbol,
                "size": max(trade_value, 1),  # Minimum size for dormant symbols
                "change": round(s.get("price_last_change_pct", 0) or 0, 2),
                "price": s.get("price_last", 0) or 0,
                "volume": s.get("trade_volume", 0) or 0,
                "eps": s.get("eps", 0) or 0,
                "peRatio": s.get("pe_ratio", 0) or 0,
                "freeFloatPct": s.get("free_float_pct", 0) or 0,
                "state": s.get("state", ""),
                "sector": sector,
            })

        # Sort sectors by total trade value
        sorted_sectors = sorted(sectors.items(), key=lambda x: sum(c["size"] for c in x[1]), reverse=True)

        # Build hierarchical structure
        children = []
        for sector_name, symbols in sorted_sectors:
            children.append({
                "name": sector_name,
                "children": symbols,
            })

        return ApiResponse[dict[str, Any]](
            success=True,
            data={"children": children},
        )
    except Exception as exc:
        logger.exception("Market treemap failed")
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"children": []},
            error={"message": str(exc)},
        )
