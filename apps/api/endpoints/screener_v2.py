"""Smart Screener V2 API — Enhanced endpoints with advanced analytics."""

from __future__ import annotations

import hashlib
import json
import time
from contextlib import aclosing
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from apps.api.error_handlers import safe_error_message
from core.config import settings
from core.logging import get_logger
from core.rate_limit import get_rate_limiter
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()

# ── Cache ──
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 60


def _cache_get(key: str) -> Any | None:
    if key in _CACHE:
        ts, val = _CACHE[key]
        if time.time() - ts < _CACHE_TTL:
            return val
        del _CACHE[key]
    return None


def _cache_set(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)
    if len(_CACHE) > 50:
        oldest = min(_CACHE, key=lambda k: _CACHE[k][0])
        del _CACHE[oldest]


# ── Rate Limiting ──
# Uses the shared core RateLimiter instead of a duplicated in-memory window.
# Limits are configurable via Settings so ops can tune without a deploy.
_RATE_LIMIT_WINDOW = settings.screener_v2_rate_window_seconds
_RATE_LIMIT_MAX = settings.screener_v2_rate_max
_screener_limiter = get_rate_limiter()


def _check_rate_limit(client_ip: str) -> bool:
    key = f"screener-v2:{client_ip}"
    if not _screener_limiter.has_limit(key):
        _screener_limiter.set_limit(
            key,
            rate=_RATE_LIMIT_MAX / _RATE_LIMIT_WINDOW,
            burst=_RATE_LIMIT_MAX,
            window_seconds=_RATE_LIMIT_WINDOW,
        )
    return _screener_limiter.allow(key)


# ── Valid sort columns ──
VALID_SORT_COLUMNS = {
    "composite_score",
    "smc_score",
    "technical_score",
    "momentum_score",
    "risk_score",
    "change_pct",
    "volume",
    "value",
    "liquidity_score",
    "power_score",
    "structure_score",
    "orderflow_score",
    "trigger_score",
    "rsi",
    "macd_histogram",
    "adx",
    "bb_pct",
    "atr_pct",
    "pe_ratio",
    "eps",
    "market_value",
    "last_price",
    "trend_strength",
    "pattern_confidence",
}


def _validate_sort_by(sort_by: str) -> str:
    if sort_by not in VALID_SORT_COLUMNS:
        return "composite_score"
    return sort_by


def _validate_sort_order(sort_order: str) -> str:
    """Whitelist sort direction. Anything invalid falls back to desc."""
    return "asc" if isinstance(sort_order, str) and sort_order.lower() == "asc" else "desc"


def _n(value: float | None, digits: int) -> float | None:
    """Round a measured value; pass an unmeasured one through as ``null``.

    ``round(None, 2)`` used to be impossible here because absence arrived as 0.0, which the
    client then drew as a real reading — RSI 0 is maximum oversold and %B 0 is a close on the
    lower band. Null is the only honest rendering of "no candles to compute on".
    """
    return None if value is None else round(value, digits)


def _item(r: Any) -> dict[str, Any]:
    """One screener row as the API returns it. Shared by GET and POST so the two never drift."""
    return {
        "symbol": r.symbol,
        "name": r.name,
        "market": r.market,
        "industry": r.industry,
        "last_price": r.last_price,
        "change_pct": r.change_pct,
        "volume": r.volume,
        "value": r.value,
        "smc_score": _n(r.smc_score, 4),
        "phase": r.phase,
        "rank": r.rank,
        "reason": r.reason,
        "liquidity_score": _n(r.liquidity_score, 4),
        "power_score": _n(r.power_score, 4),
        "structure_score": _n(r.structure_score, 4),
        "orderflow_score": _n(r.orderflow_score, 4),
        "trigger_score": _n(r.trigger_score, 4),
        "analyticsComputed": r.analytics_computed,
        "analyticsBars": r.analytics_bars,
        "rsi": _n(r.rsi, 2),
        "macd_histogram": _n(r.macd_histogram, 4),
        "bb_pct": _n(r.bb_pct, 4),
        "atr_pct": _n(r.atr_pct, 2),
        "adx": _n(r.adx, 2),
        "trend_direction": r.trend_direction,
        "trend_strength": _n(r.trend_strength, 4),
        "volatility_regime": r.volatility_regime,
        "pattern_signal": r.pattern_signal,
        "pattern_confidence": _n(r.pattern_confidence, 4),
        "technical_score": _n(r.technical_score, 4),
        "momentum_score": _n(r.momentum_score, 4),
        "risk_score": _n(r.risk_score, 4),
        "composite_score": _n(r.composite_score, 4),
        "composite_signal": r.composite_signal,
        "support_level": r.support_level,
        "resistance_level": r.resistance_level,
        "distance_to_support": r.distance_to_support,
        "distance_to_resistance": r.distance_to_resistance,
        "poc_price": r.poc_price,
        "value_area_high": r.value_area_high,
        "value_area_low": r.value_area_low,
        "volume_trend": r.volume_trend,
        "pe_ratio": r.pe_ratio,
        "eps": r.eps,
        "market_value": r.market_value,
    }


async def _fetch_v2_market_data(
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Fetch BrsApi snapshots and daily history and convert them to screener inputs.

    Uses the shared ``services.market_watch_helper`` helpers so that V2 endpoints do not
    duplicate the snapshot fetching / conversion logic already used by the main screener.

    The history map is what makes the advanced analytics real: without it every symbol was
    analysed with an empty series, so the engine's "not computed" defaults were exported as
    RSI 0.00 and ADX 0.00 for the entire market.
    """
    from brsapi.services.query_service import BrsApiQueryService
    from core.database import get_session
    from services.market_watch_helper import fetch_history_map, fetch_market_watch

    # ``get_session()`` is an async generator; ``aclosing`` guarantees the DB
    # session is closed deterministically even though we return from inside
    # the loop (relying on GC finalisation leaks the connection under load).
    async with aclosing(get_session()) as sessions:
        async for sess in sessions:
            svc = BrsApiQueryService(session=sess)
            instruments, market_watch = await fetch_market_watch(svc, limit=limit)
            symbols = {i.get("symbol") for i in instruments if i.get("symbol")}
            history_map: dict[str, list[dict[str, Any]]] = {}
            try:
                history_map = await fetch_history_map(svc, symbols=symbols)
            except Exception as exc:  # pragma: no cover - depends on the history table
                # Missing history is reported per symbol as "not measured", never filled in.
                logger.warning("Screener V2 daily history unavailable: %s", exc)
            return instruments, market_watch, history_map

    return [], [], {}


# ── Schemas ──


class ScreenerV2Request(BaseModel):
    """Request body for V2 screener filter."""

    filters: list[dict[str, Any]] = Field(default_factory=list)
    logic: str = Field("and")
    sort_by: str = Field("composite_score")
    sort_order: str = Field("desc")
    limit: int = Field(50, ge=1, le=200)
    market: str | None = None
    min_score: float = Field(0.0, ge=-1.0, le=1.0)
    include_details: bool = Field(True)
    # Advanced options
    timeframe: str = Field("daily", description="daily, weekly, monthly")
    risk_tolerance: str = Field("medium", description="low, medium, high")
    signal_filter: str | None = Field(None, description="strong_buy, buy, neutral, sell, strong_sell")


# ── Endpoints ──


@router.get(
    "",
    summary="Smart Screener V2",
    description="Enhanced screener with advanced analytics, pattern recognition, and multi-timeframe analysis.",
)
async def screener_v2(
    sort_by: str = Query("composite_score", description="Sort column"),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    min_score: float = Query(0.0, ge=-1.0, le=1.0, description="Minimum composite score"),
    market: str | None = Query(None, description="Market filter"),
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1, le=200),
    request: Request = None,
) -> ApiResponse[dict[str, Any]]:
    """Run enhanced screener with advanced analytics."""
    # Rate limiting
    client_ip = getattr(request, "client", None)
    ip = client_ip.host if client_ip else "unknown"
    if not _check_rate_limit(ip):
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": "Rate limit exceeded"})

    sort_by = _validate_sort_by(sort_by)
    sort_order = _validate_sort_order(sort_order)

    cache_key = hashlib.md5(
        f"v2:{sort_by}:{sort_order}:{limit}:{min_score}:{market}:{page}:{page_size}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    cached = _cache_get(cache_key)
    if cached:
        return ApiResponse(success=True, data=cached)

    try:
        instruments, market_watch, history_map = await _fetch_v2_market_data(limit=min(200, limit * 4))

        if not instruments:
            return ApiResponse(
                success=False, data={"items": [], "total": 0}, error={"message": "No market data available"}
            )

        from services.smart_screener_v2 import SmartScreenerV2

        screener = SmartScreenerV2()
        results, stats = screener.batch_analyze(
            instruments=instruments,
            market_watch=market_watch,
            history_map=history_map,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            min_score=min_score,
            market=market,
        )

        items = [_item(r) for r in results]

        data = {"items": items, "total": stats["total"], "stats": stats}
        _cache_set(cache_key, data)
        return ApiResponse(success=True, data=data)

    except Exception as exc:
        logger.exception("Screener V2 failed: %s", exc)
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": safe_error_message(exc)})


@router.post(
    "/filter",
    summary="Smart Screener V2 Filter",
    description="Enhanced filter with advanced criteria and analytics.",
)
async def screener_v2_filter(
    body: ScreenerV2Request,
    request: Request = None,
) -> ApiResponse[dict[str, Any]]:
    """Run enhanced screener with advanced filters."""
    client_ip = getattr(request, "client", None)
    ip = client_ip.host if client_ip else "unknown"
    if not _check_rate_limit(ip):
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": "Rate limit exceeded"})

    body.sort_by = _validate_sort_by(body.sort_by)
    body.sort_order = _validate_sort_order(body.sort_order)

    filters_key = hashlib.md5(json.dumps(body.filters, default=str).encode(), usedforsecurity=False).hexdigest()
    cache_key = hashlib.md5(
        f"v2f:{body.sort_by}:{body.sort_order}:{body.limit}:{body.min_score}:{body.market}:{filters_key}:{body.logic}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    cached = _cache_get(cache_key)
    if cached:
        return ApiResponse(success=True, data=cached)

    try:
        instruments, market_watch, history_map = await _fetch_v2_market_data(limit=min(200, body.limit * 4))

        if not instruments:
            return ApiResponse(
                success=False, data={"items": [], "total": 0}, error={"message": "No market data available"}
            )

        from services.smart_screener_v2 import SmartScreenerV2

        screener = SmartScreenerV2()

        # Apply signal filter if specified
        if body.signal_filter:
            screener.config.min_pattern_confidence = 0.5

        # Run pipeline with filters applied inside batch_analyze
        # Note: batch_analyze does NOT accept a logic/filter_logic param,
        # so OR logic must be handled here after pipeline execution.
        # First run without filters to get all scored results, then apply
        # the user's logic client-side.
        results, stats = screener.batch_analyze(
            instruments=instruments,
            market_watch=market_watch,
            history_map=history_map,
            sort_by=body.sort_by,
            sort_order=body.sort_order,
            limit=len(instruments),  # Get all results, paginate after filtering
            min_score=body.min_score,
            market=body.market,
        )

        # Apply client-side filters with correct AND/OR logic
        if body.filters:
            filtered = []
            for r in results:
                matches: list[bool] = []
                for f in body.filters:
                    field_name = f.get("field", "")
                    operator = f.get("operator", "gte")
                    value = f.get("value")
                    if value is None:
                        matches.append(True)  # Skip empty filters
                        continue
                    r_val = getattr(r, field_name, None)
                    if r_val is None:
                        r_val = r.details.get(field_name)
                    if r_val is None:
                        matches.append(False)
                        continue

                    # ── String operators (eq, neq, contains, in, not_in) ──
                    if operator in ("eq", "neq", "contains", "in", "not_in"):
                        str_r_val = str(r_val).lower()
                        str_value = str(value).lower()
                        if operator == "eq":
                            matches.append(str_r_val == str_value)
                        elif operator == "neq":
                            matches.append(str_r_val != str_value)
                        elif operator == "contains":
                            matches.append(str_value in str_r_val)
                        elif operator == "in":
                            values_list = [v.strip().lower() for v in str_value.split(",") if v.strip()]
                            matches.append(str_r_val in values_list)
                        elif operator == "not_in":
                            values_list = [v.strip().lower() for v in str_value.split(",") if v.strip()]
                            matches.append(str_r_val not in values_list)
                        else:
                            matches.append(False)
                        continue

                    # ── Numeric operators (gte, lte, gt, lt, eq, neq, between) ──
                    try:
                        num_r_val = float(r_val)
                        num_value = float(value)
                    except (TypeError, ValueError):
                        matches.append(False)
                        continue

                    if operator == "gte":
                        matches.append(num_r_val >= num_value)
                    elif operator == "lte":
                        matches.append(num_r_val <= num_value)
                    elif operator == "gt":
                        matches.append(num_r_val > num_value)
                    elif operator == "lt":
                        matches.append(num_r_val < num_value)
                    elif operator == "eq":
                        tolerance = max(abs(num_value) * 0.01, 0.001)
                        matches.append(abs(num_r_val - num_value) <= tolerance)
                    elif operator == "neq":
                        tolerance = max(abs(num_value) * 0.01, 0.001)
                        matches.append(abs(num_r_val - num_value) > tolerance)
                    elif operator == "between":
                        value_to = f.get("value_to")
                        if value_to is not None:
                            try:
                                num_value_to = float(value_to)
                                matches.append(num_value <= num_r_val <= num_value_to)
                            except (TypeError, ValueError):
                                matches.append(False)
                        else:
                            matches.append(False)
                    else:
                        # Unknown operator; fail closed
                        matches.append(False)

                # Apply AND/OR logic
                if body.logic == "or":
                    # Match if ANY filter matches
                    if matches and any(matches):
                        filtered.append(r)
                else:
                    # Match only if ALL filters match (default AND)
                    if matches and all(matches):
                        filtered.append(r)

            results = filtered

        # Paginate after filtering
        results = results[: body.limit]

        # Apply signal filter
        if body.signal_filter:
            results = [r for r in results if r.composite_signal == body.signal_filter]

        items = [_item(r) for r in results]

        data = {"items": items, "total": len(items), "stats": stats, "applied_filters": body.filters}
        _cache_set(cache_key, data)
        return ApiResponse(success=True, data=data)

    except Exception as exc:
        logger.exception("Screener V2 filter failed: %s", exc)
        return ApiResponse(success=False, data={"items": [], "total": 0}, error={"message": safe_error_message(exc)})


@router.get(
    "/compare",
    summary="Compare Symbols",
    description="Compare multiple symbols side by side with advanced analytics.",
)
async def compare_symbols(
    symbols: str = Query(..., description="Comma-separated symbol list"),
    request: Request = None,
) -> ApiResponse[dict[str, Any]]:
    """Compare multiple symbols with detailed analytics."""
    client_ip = getattr(request, "client", None)
    ip = client_ip.host if client_ip else "unknown"
    if not _check_rate_limit(ip):
        return ApiResponse(success=False, data={"items": []}, error={"message": "Rate limit exceeded"})

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if len(symbol_list) < 2 or len(symbol_list) > 10:
        return ApiResponse(success=False, data={"items": []}, error={"message": "Provide 2-10 symbols"})

    try:
        from brsapi.services.query_service import BrsApiQueryService
        from core.database import get_session

        async with aclosing(get_session()) as _sessions:
            async for sess in _sessions:
                svc = BrsApiQueryService(session=sess)
                snapshots = await svc.get_enriched_snapshots(limit=500)
                snap_map = {s.get("symbol"): s for s in snapshots if s.get("symbol") in symbol_list}

                from services.market_watch_helper import DAILY_HISTORY_DAYS, candles_from_daily_rows
                from services.smart_screener_v2 import SmartScreenerV2

                screener = SmartScreenerV2()

                results = []
                for sym in symbol_list:
                    s = snap_map.get(sym)
                    if not s:
                        continue
                    quote = {
                        "symbol": sym,
                        "price_close": s.get("price_close", 0),
                        "price_last": s.get("price_last", 0),
                        "price_change_pct": s.get("price_last_change_pct", 0),
                        "volume": s.get("trade_volume", 0),
                        "value": s.get("trade_value", 0),
                        "pe_ratio": s.get("pe_ratio"),
                        "eps": s.get("eps"),
                        "market_value": s.get("market_value"),
                    }
                    # Real candles per symbol. This endpoint used to pass an empty history, so
                    # every comparison it rendered was built from uncomputed indicators.
                    rows = await svc.get_historical_daily(sym, limit=DAILY_HISTORY_DAYS)
                    history = candles_from_daily_rows(rows)
                    result = screener.analyze_symbol(
                        sym, s.get("name", sym), s.get("market", ""), s.get("sector", ""), quote, history
                    )
                    item = _item(result)
                    results.append(item)

                return ApiResponse(success=True, data={"items": results})

    except Exception as exc:
        logger.exception("Compare symbols failed: %s", exc)
        return ApiResponse(success=False, data={"items": []}, error={"message": safe_error_message(exc)})


@router.get(
    "/sectors",
    summary="Sector Analysis",
    description="Analyze sector rotation and relative strength.",
)
async def sector_analysis(
    request: Request = None,
) -> ApiResponse[dict[str, Any]]:
    """Get sector rotation analysis."""
    client_ip = getattr(request, "client", None)
    ip = client_ip.host if client_ip else "unknown"
    if not _check_rate_limit(ip):
        return ApiResponse(success=False, data={"sectors": []}, error={"message": "Rate limit exceeded"})

    cache_key = "sectors:analysis"
    cached = _cache_get(cache_key)
    if cached:
        return ApiResponse(success=True, data=cached)

    try:
        from brsapi.services.query_service import BrsApiQueryService
        from core.database import get_session

        async with aclosing(get_session()) as _sessions:
            async for sess in _sessions:
                svc = BrsApiQueryService(session=sess)
                snapshots = await svc.get_enriched_snapshots(limit=500)

                sector_data: dict[str, dict] = {}
                for s in snapshots:
                    sector = s.get("sector", "نامشخص")
                    if not sector:
                        sector = "نامشخص"
                    if sector not in sector_data:
                        sector_data[sector] = {
                            "symbols": 0,
                            "total_change": 0,
                            "total_volume": 0,
                            "up_count": 0,
                            "total_market_value": 0,
                        }
                    sector_data[sector]["symbols"] += 1
                    sector_data[sector]["total_change"] += float(s.get("price_last_change_pct", 0) or 0)
                    sector_data[sector]["total_volume"] += int(s.get("trade_volume", 0) or 0)
                    if float(s.get("price_last_change_pct", 0) or 0) > 0:
                        sector_data[sector]["up_count"] += 1
                    sector_data[sector]["total_market_value"] += float(s.get("market_value", 0) or 0)

                sectors = []
                for name, data in sector_data.items():
                    count = data["symbols"]
                    avg_change = data["total_change"] / count if count else 0
                    breadth = data["up_count"] / count if count else 0
                    sectors.append(
                        {
                            "sector": name,
                            "symbol_count": count,
                            "avg_change_pct": round(avg_change, 2),
                            "total_volume": data["total_volume"],
                            "breadth": round(breadth, 4),
                            "total_market_value": data["total_market_value"],
                            "signal": "strong_buy"
                            if avg_change > 3 and breadth > 0.7
                            else "buy"
                            if avg_change > 1 and breadth > 0.55
                            else "sell"
                            if avg_change < -3 and breadth < 0.3
                            else "neutral",
                        }
                    )

                sectors.sort(key=lambda x: x["avg_change_pct"], reverse=True)

                data = {"sectors": sectors, "total_sectors": len(sectors)}
                _cache_set(cache_key, data)
                return ApiResponse(success=True, data=data)

    except Exception as exc:
        logger.exception("Sector analysis failed: %s", exc)
        return ApiResponse(success=False, data={"sectors": []}, error={"message": safe_error_message(exc)})
