"""Market Dashboard — Aggregated endpoint for the comprehensive dashboard view."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_brsapi_query_service, get_market_service
from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.market_service import MarketService

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "",
    summary="Market dashboard data",
    description="Aggregated market data for the main dashboard: indices, sector performance, "
    "top gainers/losers, screener, commodities, crypto, currencies, gold, and news.",
)
async def market_dashboard(
    market_service: MarketService = Depends(get_market_service),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[dict[str, Any]]:
    """Return all data needed by the dashboard in a single call."""
    results: dict[str, Any] = {}

    # Run all fetches concurrently
    async def _fetch(name: str, coro):
        try:
            results[name] = await coro
        except Exception as exc:
            logger.warning("Dashboard fetch failed for %s: %s", name, exc)
            results[name] = None

    await asyncio.gather(
        _fetch("overview", market_service.get_overview()),
        _fetch("screener", _fetch_screener_data(brsapi)),
        _fetch("commodities", brsapi.get_commodity_prices()),
        _fetch("crypto", brsapi.get_crypto_prices()),
        _fetch("gainers", market_service.get_top_gainers(20)),
        _fetch("losers", market_service.get_top_losers(20)),
        _fetch("active", market_service.get_most_active(20)),
    )

    return ApiResponse[dict[str, Any]](success=True, data=results)


async def _fetch_screener_data(brsapi) -> list[dict[str, Any]]:
    """Fetch screener data from BrsApi snapshots."""
    try:
        from services.screener_service import ScreenerService, build_quote_from_watch, build_history_from_watch
        from services.smart_money.scoring_engine import ScoringEngine

        snapshots = await brsapi.get_enriched_snapshots(limit=100)
        if not snapshots:
            return []

        engine = ScoringEngine()
        results = []
        for s in snapshots:
            sym = s.get("symbol", "")
            if not sym:
                continue
            watch = {
                "symbol": sym,
                "name": s.get("name", sym),
                "last_price": s.get("price_last", 0) or 0,
                "close": s.get("price_close", 0) or 0,
                "change": s.get("price_last_change_pct", 0) or 0,
                "change_value": s.get("price_last_change", 0) or 0,
                "volume": s.get("trade_volume", 0) or 0,
                "value": s.get("trade_value", 0) or 0,
                "high": s.get("price_highest_allowed", 0) or 0,
                "low": s.get("price_lowest_allowed", 0) or 0,
                "sector": s.get("sector", ""),
                "market": s.get("market", ""),
            }
            quote = build_quote_from_watch(watch)
            history = build_history_from_watch(watch)
            try:
                result = engine.analyze(quote, history)
                smc = result.get("smart_money_score", 0.0)
                phase = result.get("phase", "neutral")
            except Exception:
                smc = 0.0
                phase = "neutral"
            results.append({
                "symbol": sym,
                "name": s.get("name", sym),
                "sector": s.get("sector", ""),
                "price": s.get("price_last", 0) or 0,
                "change_pct": s.get("price_last_change_pct", 0) or 0,
                "volume": s.get("trade_volume", 0) or 0,
                "value": s.get("trade_value", 0) or 0,
                "smc_score": round(smc, 4),
                "phase": phase,
            })
        results.sort(key=lambda x: x["smc_score"], reverse=True)
        return results[:20]
    except Exception as exc:
        logger.warning("Screener data fetch failed: %s", exc)
        return []
