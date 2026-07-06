from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_brsapi_query_service
from schemas.common.responses import ApiResponse

router = APIRouter()

MOCK_WATCHLIST_SYMBOLS = ["فولاد", "فملی", "شپنا", "وبملت", "خودرو", "کگل", "شتران", "وغدیر"]


@router.get("/", summary="Watchlist", description="Get watchlist symbols with latest prices")
async def get_watchlist(
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    for symbol in MOCK_WATCHLIST_SYMBOLS:
        try:
            snap = await brsapi.get_enriched_symbol_detail(symbol)
            if snap:
                items.append({
                    "symbol": symbol,
                    "name": snap.get("name", f"شرکت {symbol}"),
                    "price": snap.get("price_last", 0),
                    "change": snap.get("price_last_change_pct", 0),
                    # فیلدهای غنی‌شده
                    "priceLowestAllowed": snap.get("price_lowest_allowed"),
                    "priceHighestAllowed": snap.get("price_highest_allowed"),
                    "freeFloatPct": snap.get("free_float_pct"),
                    "price_yesterday": snap.get("price_yesterday"),
                    "eps": snap.get("eps"),
                    "peRatio": snap.get("pe_ratio"),
                    "groupPeRatio": snap.get("group_pe_ratio"),
                    "psRatio": snap.get("ps_ratio"),
                    "state": snap.get("state"),
                    "sector": snap.get("sector"),
                })
            else:
                items.append({
                    "symbol": symbol,
                    "name": f"شرکت {symbol}",
                    "price": None,
                    "change": None,
                })
        except Exception:
            items.append({
                "symbol": symbol,
                "name": f"شرکت {symbol}",
                "price": None,
                "change": None,
            })
    return ApiResponse[list[dict[str, Any]]](success=True, data=items)
