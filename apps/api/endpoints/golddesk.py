"""GoldDesk — scoped-token API surface for the Gold/FX analysis environment.

منشور بخش ۴ (تجاری‌سازی):
  * جداسازی محیط تحلیلی GoldDesk با توکن‌های دامنه‌بندی‌شده (Scoped API Tokens).
  * هر مسیر حداقل یک scope از کاتالوگ ``core.security.saas.SCOPES`` می‌طلبد.
  * سطح دسترسی (tier) توکن، سقف توکن‌باکت مخصوص خودش را دارد (Free/Pro/Inst).
  * هیچ داده‌ای اینجا ساخته نمی‌شود — handlerهای واقعی ``endpoints/gold.py``
    مستقیم فراخوانی می‌شوند (DRY: منطق تجاری دقیقاً یک نسخه است).

نقاط ورود (زیر /api/v1/golddesk):
  GET /snapshot      قیمت لحظه‌ای طلا/سکه/دلار   (scope: gold:read)
  GET /nav-premium   جدول NAV Premium صندوق‌ها   (scope: gold:read)
  GET /arbitrage     اسکنر آربیتراژ ETF↔فیزیکی  (scope: gold:analyze)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_gold_live_service
from apps.api.endpoints.gold import get_arbitrage, get_etf_nav_premium, get_live_prices
from core.logging import get_logger
from core.security.saas import ScopedToken, api_key_auth
from schemas.common.responses import ApiResponse
from services.gold import GoldLiveService

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/snapshot",
    summary="اسنپ‌شات قیمت لحظه‌ای GoldDesk",
    description="قیمت لحظه‌ای طلا، سکه و دلار از BrsApi — نیازمند توکن Scoped با scope «gold:read».",
    response_model=ApiResponse[dict[str, Any]],
)
async def golddesk_snapshot(
    refresh: bool = Query(False, description="اجبار به بازخوانی از BrsApi"),
    service: GoldLiveService = Depends(get_gold_live_service),
    token: ScopedToken = Depends(api_key_auth("gold:read")),
) -> ApiResponse[dict[str, Any]]:
    data = await get_live_prices(refresh=refresh, service=service)
    return ApiResponse[dict[str, Any]](success=True, data=data.data, meta={"tier": token.tier, "owner": token.owner})


@router.get(
    "/nav-premium",
    summary="NAV Premium صندوق‌های طلا",
    description="جدول صرف/تخفیف صندوق‌های طلا نسبت به NAV — نیازمند scope «gold:read».",
    response_model=ApiResponse[dict[str, Any]],
)
async def golddesk_nav_premium(
    service: GoldLiveService = Depends(get_gold_live_service),
    token: ScopedToken = Depends(api_key_auth("gold:read")),
) -> ApiResponse[dict[str, Any]]:
    data = await get_etf_nav_premium(service=service)
    return ApiResponse[dict[str, Any]](success=True, data=data.data, meta={"tier": token.tier})


@router.get(
    "/arbitrage",
    summary="اسکنر آربیتراژ طلا",
    description="اسکن آربیتراژ ETF ↔ فیزیکی — نیازمند scope «gold:analyze».",
    response_model=ApiResponse[dict[str, Any]],
)
async def golddesk_arbitrage(
    service: GoldLiveService = Depends(get_gold_live_service),
    token: ScopedToken = Depends(api_key_auth("gold:analyze")),
) -> ApiResponse[dict[str, Any]]:
    data = await get_arbitrage(service=service)
    return ApiResponse[dict[str, Any]](success=True, data=data.data, meta={"tier": token.tier})
