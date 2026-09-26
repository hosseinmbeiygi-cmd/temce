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
    "/candles/{symbol}",
    summary="Candlestick OHLCV",
    description="Candlestick data from BrsApi (type=1 realtime 2-min, type=2 unadjusted daily, type=3 adjusted daily) for charting",
)
async def market_candles(
    symbol: str = Path(..., description="Symbol name"),
    candle_type: int = Query(3, ge=1, le=3, alias="type", description="1=realtime, 2=unadjusted, 3=adjusted"),
    limit: int = Query(300, ge=1, le=500, description="Number of bars to return"),
    service: MarketService = Depends(get_market_service),
) -> ApiResponse[list[dict[str, Any]]]:
    result = await service.get_candles(symbol, candle_type=str(candle_type), limit=limit)
    return ApiResponse[list[dict[str, Any]]](
        success=result.success,
        data=result.value if result.success else [],
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
        cached = _agg_cache_get("enriched-heatmap:500")
        if cached is not None:
            return ApiResponse[list[dict[str, Any]]](success=True, data=cached)
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
        _agg_cache_set("enriched-heatmap:500", cells)
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

        cache_key = f"treemap:{limit}"
        cached = _agg_cache_get(cache_key)
        if cached is not None:
            return ApiResponse[dict[str, Any]](success=True, data={"children": cached})
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

        _agg_cache_set(cache_key, children)
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


@router.get(
    "/flow-summary",
    summary="Real/legal money-flow summary",
    description="Market-wide net real (حقیقی) vs legal (حقوقی) flow for today plus "
    "buy/sell queue counts, from the latest brsapi_symbol_snapshots.",
)
async def market_flow_summary(
    limit: int = Query(500, ge=50, le=2000),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[dict[str, Any]]:
    """Aggregate today's real/legal net flow from live snapshots.

    Real net ≈ (buy_real_volume − sell_real_volume) × price_last; same for
    legal. Queue counts are symbols whose top bid/ask volume exceeds the
    day's traded volume (proxy for صف خرید/فروش).
    """
    try:
        # Plain snapshots (no heavy detail JOIN) — flow math only needs
        # fields that already live on SymbolSnapshotModel.
        snapshots = await brsapi.get_latest_snapshots(limit=limit)
        real_net = 0.0
        legal_net = 0.0
        queue_buy = 0
        queue_sell = 0
        for s in snapshots:
            price = s.get("price_last") or 0
            brv = s.get("buy_real_volume") or 0
            srv = s.get("sell_real_volume") or 0
            blv = s.get("buy_legal_volume") or 0
            slv = s.get("sell_legal_volume") or 0
            real_net += (brv - srv) * price
            legal_net += (blv - slv) * price
            bid_v = s.get("bid_volume_1") or 0
            ask_v = s.get("ask_volume_1") or 0
            vol = s.get("trade_volume") or 0
            if vol > 0 and bid_v > vol:
                queue_buy += 1
            if vol > 0 and ask_v > vol:
                queue_sell += 1
        return ApiResponse[dict[str, Any]](
            success=True,
            data={
                "real_net_b": round(real_net / 1e9, 1),
                "legal_net_b": round(legal_net / 1e9, 1),
                "queue_buy": queue_buy,
                "queue_sell": queue_sell,
            },
        )
    except Exception as exc:
        logger.exception("Market flow summary failed")
        return ApiResponse[dict[str, Any]](
            success=False,
            data={},
            error={"message": str(exc)},
        )


@router.get(
    "/flow-history",
    summary="Per-symbol real/legal net flow (top symbols)",
    description="Latest-day net real vs legal value per symbol from "
    "brsapi_historical_real_legal, in billion toman — strongest movers first.",
)
async def market_flow_history(
    limit: int = Query(8, ge=3, le=20),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Top symbols by |net real flow| for the latest synced date."""
    try:
        from sqlalchemy import func, select

        from brsapi.models.tsetmc import HistoricalRealLegalModel

        latest_date = (
            await brsapi.session.execute(select(func.max(HistoricalRealLegalModel.date)))
        ).scalar_one_or_none()
        if not latest_date:
            return ApiResponse[dict[str, Any] | list[dict[str, Any]]](success=True, data=[])  # type: ignore[arg-type]

        stmt = (
            select(HistoricalRealLegalModel)
            .where(HistoricalRealLegalModel.date == latest_date)
        )
        rows = (await brsapi.session.execute(stmt)).scalars().all()

        flows: list[dict[str, Any]] = []
        for r in rows:
            real_net = (r.buy_real_value or 0) - (r.sell_real_value or 0)
            legal_net = (r.buy_legal_value or 0) - (r.sell_legal_value or 0)
            if real_net == 0 and legal_net == 0:
                continue
            flows.append({
                "symbol": r.symbol,
                "real_net_b": round(real_net / 1e9, 1),
                "legal_net_b": round(legal_net / 1e9, 1),
            })
        flows.sort(key=lambda x: abs(x["real_net_b"]), reverse=True)
        return ApiResponse[list[dict[str, Any]]](success=True, data=flows[:limit])
    except Exception as exc:
        logger.exception("Market flow history failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/index-history/{name}",
    summary="Index value history",
    description="Latest N index values for one index (e.g. شاخص کل) — intraday "
    "snapshots taken by the BrsApi sync, oldest-first, for area charts.",
)
async def market_index_history(
    name: str = Path(..., description="Index name, e.g. شاخص کل"),
    limit: int = Query(60, ge=10, le=300),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        rows = await brsapi.get_index_history(name, limit=limit)
        rows.reverse()  # oldest-first for charting
        return ApiResponse[list[dict[str, Any]]](success=True, data=rows)
    except Exception as exc:
        logger.exception("Index history failed for %s", name)
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


def _classify_asset(name: str) -> str | None:
    """Approximate asset-class bucket from a symbol's Persian company name.

    TSE has no clean asset-class feed, so we classify from the name:
      * «سرمایه‌گذاری»-prefixed companies    → سرمایه‌گذاری (holding)
      * fund markers (صندوق/ETF + نوع)      → one of the fund classes
      * everything else                      → سهام (common equity)

    Returns None when the name clearly belongs to a non-tradable record
    (rights/حق تقدم, ETF unit suffixes handled by fund branch, etc.) so the
    caller can skip it instead of polluting the equity bucket.
    """
    n = (name or "").strip()
    if not n:
        return None
    if "حق تقدم" in n:
        return None
    # Fund branch first: fund names may contain «سرمایه‌گذاری» (e.g.
    # «صندوق سرمایه‌گذاری طلا») and must classify as funds, not holdings.
    if "صندوق" in n:
        if "طلا" in n:
            return "صندوق طلا"
        if "درآمد ثابت" in n or "درامد ثابت" in n:
            return "اوراق درآمد ثابت"
        return "صندوق سهامی"
    if "سرمایه‌گذاری" in n or "سرمایه گذاری" in n:
        return "سرمایه‌گذاری"
    if "اوراق" in n:
        return "اوراق درآمد ثابت"
    return "سهام"


# ── Aggregate-endpoint cache ─────────────────────────────────────────────
# The snapshot feed refreshes every few minutes, so the dashboard
# aggregates below cache their result briefly: a 5-minute TTL keeps
# numbers fresh without re-running the aggregation on every widget poll
# (and shields the DB when several clients hit the widgets at once).
_AGG_CACHE: dict[str, tuple[float, Any]] = {}
_AGG_TTL = 300.0  # seconds


def _agg_cache_get(key: str) -> Any | None:
    import time

    hit = _AGG_CACHE.get(key)
    if hit and (time.monotonic() - hit[0]) < _AGG_TTL:
        return hit[1]
    return None


def _agg_cache_set(key: str, val: Any) -> None:
    import time

    _AGG_CACHE[key] = (time.monotonic(), val)
    # Bound the cache (only a few keys exist, but stay defensive).
    while len(_AGG_CACHE) > 8:
        oldest = min(_AGG_CACHE, key=lambda k: _AGG_CACHE[k][0])
        del _AGG_CACHE[oldest]


def _fa_weekday(date_str: str) -> str:
    """Persian weekday label for a stored history date.

    BrsApi history rows carry **Jalali** dates (e.g. ``1405-06-18``), so the
    digits are first converted to Gregorian via ``jdatetime`` before the
    weekday is derived. Plain Gregorian dates (year ≥ 1700) are handled
    directly. Anything unparsable falls back to the raw string so the chart
    still shows a label.
    """
    digits = "".join(ch for ch in str(date_str) if ch.isdigit())
    if len(digits) < 8:
        return str(date_str)
    y, m, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
    weekdays = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
    try:
        if 1300 <= y <= 1600:  # Jalali year range
            import jdatetime

            return weekdays[jdatetime.date(y, m, d).togregorian().weekday()]
        from datetime import date as _date

        return weekdays[_date(y, m, d).weekday()]
    except (ValueError, ImportError):
        return str(date_str)


@router.get(
    "/asset-allocation",
    summary="Market-wide asset-class allocation",
    description="Aggregate market_value of all listed instruments grouped into "
    "five asset classes (سهام، سرمایه‌گذاری، صندوق سهامی، صندوق طلا، "
    "اوراق درآمد ثابت) from the latest brsapi_symbol_snapshots cycle.",
)
async def market_asset_allocation(
    limit: int = Query(2000, ge=100, le=5000),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Market-cap allocation across asset classes.

    Classification is name-based (see :func:`_classify_asset`) — an
    approximation while TSE offers no asset-class field. Percentages are
    computed server-side; the frontend renders the donut directly.
    """
    try:
        cached = _agg_cache_get("asset-allocation")
        if cached is not None:
            return ApiResponse[list[dict[str, Any]]](success=True, data=cached)
        # Plain snapshots (no heavy detail JOIN) — classification and
        # market_value both come from SymbolSnapshotModel itself.
        snapshots = await brsapi.get_latest_snapshots(limit=limit)
        buckets: dict[str, float] = {}
        for s in snapshots:
            mv = s.get("market_value") or 0
            cls = _classify_asset(s.get("name") or "")
            if not mv or cls is None:
                continue
            buckets[cls] = buckets.get(cls, 0.0) + mv
        total = sum(buckets.values())
        if total <= 0:
            return ApiResponse[list[dict[str, Any]]](success=True, data=[])
        rows = [
            {
                "label": label,
                "value_b": round(net / 1e12, 0),  # هزار میلیارد تومان
                "pct": round(net / total * 100, 1),
            }
            for label, net in buckets.items()
        ]
        rows.sort(key=lambda x: x["value_b"], reverse=True)
        _agg_cache_set("asset-allocation", rows)
        return ApiResponse[list[dict[str, Any]]](success=True, data=rows)
    except Exception as exc:
        logger.exception("Asset allocation failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/cashflow-by-sector",
    summary="Real money flow by sector (today)",
    description="Net real (حقیقی) value flow grouped by industry sector for the "
    "latest snapshot cycle, in billion toman — from brsapi_symbol_snapshots.",
)
async def market_cashflow_by_sector(
    limit: int = Query(500, ge=50, le=2000),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Per-sector net real flow: (buy_real_volume − sell_real_volume) × price_last."""
    try:
        cached = _agg_cache_get("cashflow-by-sector")
        if cached is not None:
            return ApiResponse[list[dict[str, Any]]](success=True, data=cached)
        # Plain snapshots (no heavy detail JOIN) — sector/flow fields are
        # already on SymbolSnapshotModel.
        snapshots = await brsapi.get_latest_snapshots(limit=limit)
        sectors: dict[str, float] = {}
        for s in snapshots:
            price = s.get("price_last") or 0
            brv = s.get("buy_real_volume") or 0
            srv = s.get("sell_real_volume") or 0
            if not price or (brv == 0 and srv == 0):
                continue
            sector = (s.get("sector") or "").strip() or "سایر"
            sectors[sector] = sectors.get(sector, 0.0) + (brv - srv) * price
        rows = [
            {"name": name, "value_b": round(net / 1e9, 1)}
            for name, net in sectors.items()
        ]
        rows.sort(key=lambda x: x["value_b"], reverse=True)
        rows = rows[:20]
        _agg_cache_set("cashflow-by-sector", rows)
        return ApiResponse[list[dict[str, Any]]](success=True, data=rows)
    except Exception as exc:
        logger.exception("Cashflow by sector failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/value-history",
    summary="Daily market trade value (last N trading days)",
    description="Market-wide trade_value summed over all symbols per day from "
    "brsapi_historical_daily — oldest-first, in billion toman, for bar charts.",
)
async def market_value_history(
    days: int = Query(5, ge=3, le=30),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        from sqlalchemy import func, select

        from brsapi.models.tsetmc import HistoricalDailyModel

        # Partition key → the latest ``days`` distinct trading dates.
        latest_dates = (
            await brsapi.session.execute(
                select(HistoricalDailyModel.date)
                .distinct()
                .order_by(HistoricalDailyModel.date.desc())
                .limit(days)
            )
        ).scalars().all()
        if not latest_dates:
            return ApiResponse[list[dict[str, Any]]](success=True, data=[])

        stmt = (
            select(
                HistoricalDailyModel.date,
                func.sum(HistoricalDailyModel.trade_value).label("total_value"),
            )
            .where(HistoricalDailyModel.date.in_(latest_dates))
            .group_by(HistoricalDailyModel.date)
            .order_by(HistoricalDailyModel.date.asc())
        )
        rows = (await brsapi.session.execute(stmt)).all()

        data: list[dict[str, Any]] = []
        for r in rows:
            data.append({
                "date": str(r.date),
                "day": _fa_weekday(r.date),
                "value_b": round((r.total_value or 0) / 1e9, 0),
            })
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        logger.exception("Market value history failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/ownership-history",
    summary="Daily real/legal net flow (last N trading days)",
    description="Market-wide net real (حقیقی) vs legal (حقوقی) value per day from "
    "brsapi_historical_real_legal — oldest-first, in billion toman.",
)
async def market_ownership_history(
    days: int = Query(5, ge=3, le=30),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    try:
        from sqlalchemy import func, select

        from brsapi.models.tsetmc import HistoricalRealLegalModel

        latest_dates = (
            await brsapi.session.execute(
                select(HistoricalRealLegalModel.date)
                .distinct()
                .order_by(HistoricalRealLegalModel.date.desc())
                .limit(days)
            )
        ).scalars().all()
        if not latest_dates:
            return ApiResponse[list[dict[str, Any]]](success=True, data=[])

        stmt = (
            select(
                HistoricalRealLegalModel.date,
                func.sum(HistoricalRealLegalModel.buy_real_value).label("real_buy"),
                func.sum(HistoricalRealLegalModel.sell_real_value).label("real_sell"),
                func.sum(HistoricalRealLegalModel.buy_legal_value).label("legal_buy"),
                func.sum(HistoricalRealLegalModel.sell_legal_value).label("legal_sell"),
            )
            .where(HistoricalRealLegalModel.date.in_(latest_dates))
            .group_by(HistoricalRealLegalModel.date)
            .order_by(HistoricalRealLegalModel.date.asc())
        )
        rows = (await brsapi.session.execute(stmt)).all()

        data: list[dict[str, Any]] = []
        for r in rows:
            data.append({
                "date": str(r.date),
                "day": _fa_weekday(r.date),
                "real_b": round(((r.real_buy or 0) - (r.real_sell or 0)) / 1e9, 1),
                "legal_b": round(((r.legal_buy or 0) - (r.legal_sell or 0)) / 1e9, 1),
            })
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        logger.exception("Market ownership history failed")
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})
