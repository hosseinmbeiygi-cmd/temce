from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies import get_brsapi_query_service
from core.logging import get_logger
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)
router = APIRouter()


def _fund_list_row(fund: dict[str, Any]) -> dict[str, Any]:
    """یک ردیف از فهرست صندوق‌های ``/market-info/funds``.

    جدول ``brsapi_ime_funds`` هیچ ستون NAV ندارد و فقط قیمت معامله‌شده را نگه
    می‌دارد. این فهرست قبلاً ``price_last`` را زیر کلید ``nav`` منتشر می‌کرد؛ هر
    مصرف‌کننده‌ای که ``price/nav - 1`` می‌ساخت برای همهٔ صندوق‌ها دقیقاً صفر
    می‌گرفت (ISSUE-128: در ۳۲ از ۳۲ صندوق ``nav == price_last``).

    اکنون قیمت با نام خودش برمی‌گردد و ``nav`` تا وقتی NAV واقعی
    (``brsapi_nav_records``) به این مسیر join نشده ``None`` می‌ماند — «NAV
    ناموجود» نباید با «حباب صفر» اشتباه شود.
    """
    return {
        "symbol": fund.get("symbol", ""),
        "name": fund.get("name", ""),
        "date": fund.get("date", ""),
        "nav": None,
        "nav_source": None,
        "price_last": fund.get("price_last"),
        "price_close": fund.get("price_close"),
    }


@router.get("/industries", summary="List industries", description="List all industries sorted by count")
async def list_industries(
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    try:
        categories = await brsapi.get_commodity_categories()
        items = sorted(
            [{"name": cat.get("category", "سایر"), "count": cat.get("count", 0), "last_update": cat.get("last_update", "")}
             for cat in categories],
            key=lambda x: x["count"],
            reverse=True,
        ) if categories else []
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=True,
            data=PaginatedResult(items=items, total=len(items), page=1, page_size=50, total_pages=1),
        )
    except Exception:
        logger.exception("Failed to fetch industries")
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1),
            error={"message": "Failed to load industries"},
        )


@router.get("/funds", summary="List funds", description="List all funds")
async def list_funds(
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    try:
        funds = await brsapi.get_ime_funds()
        # Deduplicate by symbol — keep the LATEST snapshot per fund.
        # brsapi_ime_funds stores one row per fetch cycle, so each symbol
        # appears dozens/hundreds of times. Keep the row with the greatest
        # ``fetched_at`` — insertion order is not guaranteed by the query.
        latest_by_symbol: dict[str, dict[str, Any]] = {}
        for f in funds:
            sym = f.get("symbol", "")
            if not sym:
                continue
            previous = latest_by_symbol.get(sym)
            if previous is None or str(f.get("fetched_at") or "") >= str(previous.get("fetched_at") or ""):
                latest_by_symbol[sym] = f
        items = [_fund_list_row(f) for f in latest_by_symbol.values()]
        items.sort(key=lambda x: x["price_last"] or x["price_close"] or 0, reverse=True)
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=True,
            data=PaginatedResult(items=items, total=len(items), page=1, page_size=50, total_pages=1),
        )
    except Exception:
        logger.exception("Failed to fetch funds")
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1),
            error={"message": "Failed to load funds"},
        )
