from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from schemas.common.responses import ApiResponse
from services.screener_service import ScreenerService

router = APIRouter()


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
) -> ApiResponse[dict[str, Any]]:
    """Run the 5-phase Smart Money screener over enriched market data."""
    try:
        # ── 1. Fetch real enriched market data (from BrsApi) ──
        from core.database import get_session

        instruments: list[dict[str, Any]] = []
        market_watch: list[dict[str, Any]] = []

        async for session in get_session():
            from brsapi.services.query_service import BrsApiQueryService

            svc = BrsApiQueryService(session=session)
            snapshots = await svc.get_enriched_snapshots(limit=200)

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
                    watch_item = {
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
                    market_watch.append(watch_item)

        if not instruments:
            return ApiResponse[dict[str, Any]](
                success=False,
                data={"items": [], "total": 0},
                error={"message": "No market data available for screening"},
            )

        # ── 2. Run screener pipeline ──
        svc = ScreenerService()
        results = svc.screen(
            instruments=instruments,
            market_watch=market_watch,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            min_score=min_score,
            market=market,
        )

        # ── 3. Serialise ──
        from dataclasses import asdict

        items = [asdict(r) for r in results]
        return ApiResponse[dict[str, Any]](
            success=True,
            data={
                "items": items,
                "total": len(items),
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        )
    except Exception as exc:
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"items": [], "total": 0},
            error={"message": str(exc)},
        )
