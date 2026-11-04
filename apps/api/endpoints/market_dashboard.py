"""Market Dashboard — Aggregated endpoint for the comprehensive dashboard view."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_brsapi_query_service, get_market_service
from core.currency import rial_to_toman_float
from core.freshness import newest_fetched_at
from core.logging import get_logger
from core.result import Result
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
    errors: dict[str, str] = {}

    # Run all fetches concurrently
    async def _fetch(name: str, coro):
        try:
            value = await coro
        except Exception as exc:
            logger.warning("Dashboard fetch failed for %s: %s", name, exc)
            results[name] = None
            errors[name] = str(exc)
            return
        # Service-layer failures are Result.fail, not exceptions. Keep the
        # Result envelope the frontend already reads (``overview.value``) but
        # record the failure so the dashboard cannot claim all-success.
        if isinstance(value, Result) and not value.success:
            errors[name] = value.error or "source failed"
        results[name] = value

    await asyncio.gather(
        _fetch("overview", market_service.get_overview()),
        _fetch("indices", _unwrap_indices(market_service)),
        _fetch("screener", _fetch_screener_data(brsapi)),
        _fetch("commodities", brsapi.get_commodity_prices()),
        _fetch("crypto", brsapi.get_crypto_prices()),
        _fetch("gainers", market_service.get_top_gainers(20)),
        _fetch("losers", market_service.get_top_losers(20)),
        _fetch("active", market_service.get_most_active(20)),
    )

    payload = dict(results)
    if errors:
        payload["errors"] = errors

    # Envelope freshness: the overview section computes it from the snapshot
    # rows it served; indices rows are the fallback. Without this the dashboard
    # payload had no source timestamp at all (audit API-04).
    overview_result = results.get("overview")
    data_as_of: str | None = None
    if isinstance(overview_result, Result) and overview_result.success and isinstance(overview_result.value, dict):
        data_as_of = overview_result.value.get("data_as_of")
    if data_as_of is None:
        data_as_of = newest_fetched_at(results.get("indices"))

    def _failed(value: Any) -> bool:
        return value is None or (isinstance(value, Result) and not value.success)

    if all(_failed(value) for value in results.values()):
        return ApiResponse[dict[str, Any]](
            success=False,
            data=payload,
            data_as_of=data_as_of,
            error={"message": "All dashboard sources failed", "sources": errors},
        )
    return ApiResponse[dict[str, Any]](success=True, data=payload, data_as_of=data_as_of)


async def _unwrap_indices(market_service: MarketService) -> list[dict[str, Any]]:
    """Get indices from DB, unwrapping the Result object."""
    result = await market_service.get_index_values()
    if not result.success:
        raise RuntimeError(result.error or "index values unavailable")
    return result.value or []


async def _fetch_screener_data(brsapi) -> list[dict[str, Any]]:
    """Fetch screener data from BrsApi snapshots using real data."""
    try:
        from services.screener_service import build_real_quote_from_snapshot
        from services.smart_money.scoring_engine import ScoringEngine

        snapshots = await brsapi.get_enriched_snapshots(limit=500)
        if not snapshots:
            return []

        engine = ScoringEngine()
        results = []
        for s in snapshots:
            sym = s.get("symbol", "")
            if not sym:
                continue
            # Build quote directly from real snapshot data (no synthetic fields)
            quote = build_real_quote_from_snapshot(s)
            try:
                # Dashboard uses partial mode (empty history) for speed
                result = engine.analyze(quote, [])
                smc = result.get("smart_money_score", 0.0)
                phase = result.get("phase", "neutral")
            except Exception as exc:
                logger.debug("Scoring failed for %s: %s", sym, exc)
                smc = 0.0
                phase = "neutral"
            results.append({
                "symbol": sym,
                "name": s.get("name", sym),
                "sector": s.get("sector", ""),
                "price": s.get("price_last", 0) or 0,
                "price_toman": rial_to_toman_float(s.get("price_last") or 0),
                "change_pct": s.get("price_last_change_pct", 0) or 0,
                "volume": s.get("trade_volume", 0) or 0,
                "value": s.get("trade_value", 0) or 0,
                "value_toman": rial_to_toman_float(s.get("trade_value") or 0),
                "currency": "TMN",
                "smc_score": round(smc, 4),
                "phase": phase,
            })
        results.sort(key=lambda x: x["smc_score"], reverse=True)
        return results[:20]
    except Exception as exc:
        logger.warning("Screener data fetch failed: %s", exc)
        raise
