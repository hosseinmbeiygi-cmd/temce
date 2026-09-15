from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from fastapi import APIRouter, Query, Request

from core.logging import get_logger
from core.rate_limit import get_rate_limiter
from schemas.api.screener_filter import (
    FilteredItem,
    ScreenerFilterRequest,
    ScreenerFilterResponse,
    ScreenerFilterStats,
)
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()

# ── Simple in-memory cache for screener results (TTL = 60s) ──
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 60  # seconds

# ── Valid sort columns ──
VALID_SORT_COLUMNS = {
    "smc_score",
    "change_pct",
    "volume",
    "value",
    "liquidity_score",
    "power_score",
    "structure_score",
    "orderflow_score",
    "trigger_score",
    "pe_ratio",
    "eps",
    "market_value",
    "last_price",
}


def _validate_sort_by(sort_by: str) -> str:
    """Validate sort_by column name to prevent injection."""
    if sort_by not in VALID_SORT_COLUMNS:
        return "smc_score"  # default
    return sort_by


# ── Rate limiting (per-IP, sliding window) ──
# Uses the shared core RateLimiter instead of a duplicated in-memory window.
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 30  # max requests per window
_screener_limiter = get_rate_limiter()


def _check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit. Returns True if allowed."""
    key = f"screener:{client_ip}"
    if not _screener_limiter.has_limit(key):
        _screener_limiter.set_limit(
            key,
            rate=_RATE_LIMIT_MAX / _RATE_LIMIT_WINDOW,
            burst=_RATE_LIMIT_MAX,
            window_seconds=_RATE_LIMIT_WINDOW,
        )
    return _screener_limiter.allow(key)


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


async def _fetch_screen_data_with_session(
    session: AsyncSession,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load market data using an externally-managed session."""
    from brsapi.services.query_service import BrsApiQueryService
    from services.market_watch_helper import fetch_market_watch

    svc = BrsApiQueryService(session=session)
    return await fetch_market_watch(svc, limit=limit)


@router.get(
    "",
    summary="Stock screener",
    description="Run the 5-phase Smart Money screener pipeline and return scored symbols with sparklines.",
)
async def screener(
    sort_by: str = Query("smc_score", description="Sort column"),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum SMC score filter"),
    market: str | None = Query(None, description="Market filter (e.g. BOURS, FARA)"),
    page: int | None = Query(None, ge=1, description="Page number (1-indexed)"),
    page_size: int | None = Query(None, ge=1, le=200, description="Page size"),
    request: Request = None,
) -> ApiResponse[dict[str, Any]]:
    """Run the 5-phase Smart Money screener over real market data."""
    # Rate limiting
    client_ip = getattr(request, "client", None)
    ip = client_ip.host if client_ip else "unknown"
    if not _check_rate_limit(ip):
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"items": [], "total": 0},
            error={"message": "Rate limit exceeded. Please wait before making more requests."},
        )

    # Validate sort_by
    sort_by = _validate_sort_by(sort_by)

    cache_key = hashlib.md5(
        f"screen:{sort_by}:{sort_order}:{limit}:{min_score}:{market}:{page}:{page_size}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    cached = _cache_get(cache_key)
    if cached is not None:
        return ApiResponse[dict[str, Any]](success=True, data=cached)

    try:
        # ── 1. Fetch market data + keep DB session open ──
        from core.database import get_session

        async with get_session() as session:
            instruments, market_watch = await _fetch_screen_data_with_session(session, limit=min(200, limit * 4))

            if not instruments:
                logger.warning("Screener: no market data available (DB may be empty or not synced)")
                return ApiResponse[dict[str, Any]](
                    success=False,
                    data={"items": [], "total": 0},
                    error={"message": "No market data available for screening. Please ensure BrsApi sync has run."},
                )

            # ── 2. Run screener pipeline with real data ──
            from services.screener_service import ScreenerService

            svc = ScreenerService(session=session, history_limit=60)
            results, pagination_info = await svc.screen(
                instruments=instruments,
                market_watch=market_watch,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
                min_score=min_score,
                market=market,
                page=page,
                page_size=page_size,
            )
        # ── session closed here ──

        from dataclasses import asdict

        items = [asdict(r) for r in results]
        data = {
            "items": items,
            "total": pagination_info.get("total", len(items)),
            "page": pagination_info.get("page", 1),
            "page_size": pagination_info.get("page_size", limit),
            "total_pages": pagination_info.get("total_pages", 1),
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        _cache_set(cache_key, data)
        return ApiResponse[dict[str, Any]](success=True, data=data)
    except Exception as exc:
        logger.exception("Screener GET failed: %s", exc)
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"items": [], "total": 0},
            error={"message": f"Screener pipeline error: {exc}"},
        )


@router.post(
    "/filter",
    summary="Dynamic screener filter",
    description="Filter screened symbols with dynamic criteria (RSI, P/E, volume, etc.) using real data.",
)
async def screener_filter(
    body: ScreenerFilterRequest,
    request: Request = None,
) -> ApiResponse[ScreenerFilterResponse]:
    """Run the screener pipeline and apply user-defined filters on real data."""
    # Rate limiting
    client_ip = getattr(request, "client", None)
    ip = client_ip.host if client_ip else "unknown"
    if not _check_rate_limit(ip):
        return ApiResponse[ScreenerFilterResponse](
            success=False,
            data=ScreenerFilterResponse(items=[], total=0),
            error={"message": "Rate limit exceeded. Please wait before making more requests."},
        )

    # Validate sort_by
    body.sort_by = _validate_sort_by(body.sort_by)

    filters_key = hashlib.md5(
        json.dumps(
            [
                {"field": f.field, "operator": f.operator, "value": f.value, "value_to": f.value_to}
                for f in body.filters
            ],
            default=str,
        ).encode(),
        usedforsecurity=False,
    ).hexdigest()
    cache_key = hashlib.md5(
        f"filter:{body.sort_by}:{body.sort_order}:{body.limit}:{body.min_score}:{body.market}:{filters_key}:{body.logic}:{body.include_details}".encode(),
        usedforsecurity=False,
    ).hexdigest()
    cached = _cache_get(cache_key)
    if cached is not None:
        return ApiResponse[ScreenerFilterResponse](success=True, data=cached)

    try:
        # ── 1. Fetch market data + keep DB session open ──
        from core.database import get_session

        async with get_session() as session:
            instruments, market_watch = await _fetch_screen_data_with_session(session, limit=min(200, body.limit * 4))

            if not instruments:
                logger.warning("Screener filter: no market data available")
                return ApiResponse[ScreenerFilterResponse](
                    success=False,
                    data=ScreenerFilterResponse(items=[], total=0),
                    error={
                        "message": "No market data available. Please ensure BrsApi sync has run and DB is populated."
                    },
                )

            # ── 2. Convert request filters to dicts ──
            filter_dicts = []
            for f in body.filters:
                fd = {"field": f.field, "operator": f.operator, "value": f.value}
                if f.value_to is not None:
                    fd["value_to"] = f.value_to
                filter_dicts.append(fd)

            # ── 3. Run pipeline with real data ──
            from services.screener_service import ScreenerService

            svc = ScreenerService(session=session, history_limit=60)
            results, stats_raw = await svc.screen_with_filters(
                instruments=instruments,
                market_watch=market_watch,
                filters=filter_dicts if filter_dicts else None,
                filter_logic=body.logic,
                sort_by=body.sort_by,
                sort_order=body.sort_order,
                limit=body.limit,
                min_score=body.min_score,
                market=body.market,
                include_details=body.include_details,
            )
        # ── session closed here ──

        # ── 4. Build response ──
        items = []
        for r in results:
            details = r.details or {}
            trade_count_raw = details.get("trade_count")
            item = FilteredItem(
                symbol=r.symbol,
                name=r.name,
                market=r.market,
                industry=r.industry,
                last_price=r.last_price,
                change_pct=r.change_pct,
                volume=r.volume,
                value=r.value,
                smc_score=r.smc_score,
                phase=r.phase,
                rank=r.rank,
                reason=r.reason,
                liquidity_score=r.liquidity_score,
                power_score=r.power_score,
                structure_score=r.structure_score,
                orderflow_score=r.orderflow_score,
                trigger_score=r.trigger_score,
                pe_ratio=details.get("pe_ratio"),
                eps=details.get("eps"),
                market_value=details.get("market_value"),
                trade_count=int(trade_count_raw) if trade_count_raw is not None else None,
                # V2 advanced analytics (may be present if V2 engine was used)
                rsi=details.get("rsi"),
                macd_histogram=details.get("macd_histogram"),
                bb_pct=details.get("bb_pct"),
                atr_pct=details.get("atr_pct"),
                adx=details.get("adx"),
                trend_direction=details.get("trend_direction"),
                trend_strength=details.get("trend_strength"),
                volatility_regime=details.get("volatility_regime"),
                pattern_signal=details.get("pattern_signal"),
                pattern_confidence=details.get("pattern_confidence"),
                technical_score=details.get("technical_score"),
                momentum_score=details.get("momentum_score"),
                risk_score=details.get("risk_score"),
                composite_score=details.get("composite_score"),
                composite_signal=details.get("composite_signal"),
                support_level=details.get("support_level"),
                resistance_level=details.get("resistance_level"),
                distance_to_support=details.get("distance_to_support"),
                distance_to_resistance=details.get("distance_to_resistance"),
                poc_price=details.get("poc_price"),
                value_area_high=details.get("value_area_high"),
                value_area_low=details.get("value_area_low"),
                volume_trend=details.get("volume_trend"),
                details=details,
            )
            items.append(item)

        stats = ScreenerFilterStats(**stats_raw)

        response_data = ScreenerFilterResponse(
            items=items,
            total=len(items),
            stats=stats,
            applied_filters=body.filters,
        )
        _cache_set(cache_key, response_data.model_dump())

        return ApiResponse[ScreenerFilterResponse](
            success=True,
            data=response_data,
        )
    except Exception as exc:
        logger.exception("Screener filter POST failed: %s", exc)
        return ApiResponse[ScreenerFilterResponse](
            success=False,
            data=ScreenerFilterResponse(items=[], total=0),
            error={"message": f"Screener filter error: {exc}"},
        )
