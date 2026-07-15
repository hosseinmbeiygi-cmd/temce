from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Query

from core.logging import get_logger
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


async def _fetch_screen_data(limit: int = 200) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Any]:
    """Fetch instruments + market_watch from BrsApi with fallback.

    Returns (instruments, market_watch, session) — session is kept open
    so ScreenerService can query historical tables.
    """
    from core.database import get_session

    instruments: list[dict[str, Any]] = []
    market_watch: list[dict[str, Any]] = []
    session = None

    async for sess in get_session():
        session = sess
        from brsapi.services.query_service import BrsApiQueryService

        svc = BrsApiQueryService(session=sess)

        try:
            snapshots = await svc.get_enriched_snapshots(limit=limit)
        except Exception:
            snapshots = await svc.get_latest_snapshots(limit=limit)

        if snapshots:
            for s in snapshots:
                sym = s.get("symbol", "")
                if not sym:
                    continue
                instrument = {
                    "symbol": sym,
                    "name": s.get("name", sym),
                    "market": s.get("market", ""),
                    "industry": s.get("sector", ""),
                }
                instruments.append(instrument)
                # Pass the full snapshot row as watch_item (for filter lookups)
                watch_item = {
                    "symbol": sym,
                    "name": s.get("name", sym),
                    "last_price": s.get("price_last", 0) or 0,
                    "close": s.get("price_close", 0) or 0,
                    "change": s.get("price_last_change_pct", 0) or 0,
                    "change_value": s.get("price_last_change", 0) or 0,
                    "volume": s.get("trade_volume", 0) or 0,
                    "value": s.get("trade_value", 0) or 0,
                    "high": s.get("price_max", 0) or 0,
                    "low": s.get("price_min", 0) or 0,
                    "sector": s.get("sector", ""),
                    "market": s.get("market", ""),
                    "pe_ratio": s.get("pe_ratio"),
                    "eps": s.get("eps"),
                    "market_value": s.get("market_value"),
                    "trade_count": s.get("trade_count"),
                    "price_first": s.get("price_first"),
                    "price_yesterday": s.get("price_yesterday"),
                    "price_min": s.get("price_min"),
                    "price_max": s.get("price_max"),
                    "shares_count": s.get("shares_count"),
                    # Raw snapshot for quote building
                    "_snapshot": s,
                }
                market_watch.append(watch_item)
        break

    return instruments, market_watch, session


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
) -> ApiResponse[dict[str, Any]]:
    """Run the 5-phase Smart Money screener over real market data."""
    cache_key = f"screen:{sort_by}:{sort_order}:{limit}:{min_score}:{market}:{page}:{page_size}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return ApiResponse[dict[str, Any]](success=True, data=cached)

    try:
        # ── 1. Fetch market data + keep DB session open ──
        instruments, market_watch, session = await _fetch_screen_data(limit=min(200, limit * 4))

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

        # ── 3. Serialise ──
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
) -> ApiResponse[ScreenerFilterResponse]:
    """Run the screener pipeline and apply user-defined filters on real data."""
    filters_key = json.dumps([{"field": f.field, "operator": f.operator, "value": f.value, "value_to": f.value_to} for f in body.filters], default=str)
    cache_key = f"filter:{body.sort_by}:{body.sort_order}:{body.limit}:{body.min_score}:{body.market}:{filters_key}:{body.logic}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return ApiResponse[ScreenerFilterResponse](success=True, data=cached)

    try:
        # ── 1. Fetch market data + keep DB session open ──
        instruments, market_watch, session = await _fetch_screen_data(limit=min(200, body.limit * 4))

        if not instruments:
            logger.warning("Screener filter: no market data available")
            return ApiResponse[ScreenerFilterResponse](
                success=False,
                data=ScreenerFilterResponse(items=[], total=0),
                error={"message": "No market data available. Please ensure BrsApi sync has run and DB is populated."},
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

        # ── 4. Build response ──
        items = []
        for r in results:
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
                pe_ratio=r.details.get("pe_ratio"),
                eps=r.details.get("eps"),
                market_value=r.details.get("market_value"),
                trade_count=int(r.details.get("trade_count", 0)) if r.details.get("trade_count") else None,
                details=r.details,
            )
            items.append(item)

        stats = ScreenerFilterStats(**stats_raw)

        response_data = ScreenerFilterResponse(
            items=items,
            total=len(items),
            stats=stats,
            applied_filters=body.filters,
        )
        _cache_set(cache_key, response_data)

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
