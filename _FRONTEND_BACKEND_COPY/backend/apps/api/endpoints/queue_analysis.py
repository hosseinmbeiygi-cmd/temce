"""
📊 Queue Analysis API — تحلیل صف‌های خرید و فروش در بورس تهران

Endpoints:
  GET /queue-analysis/market     — آمار کلی صف‌های بازار
  GET /queue-analysis/batch      — تحلیل صف گروهی از نمادها
  GET /queue-analysis/{symbol}   — تحلیل صف برای یک نماد خاص

(مهم: route /market و /batch باید قبل از /{symbol} تعریف شود)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_brsapi_query_service, get_db_session
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_queue_analysis_service(
    brsapi=Depends(get_brsapi_query_service),
    db_session: AsyncSession = Depends(get_db_session),
):
    from services.queue_analysis_service import QueueAnalysisService

    return QueueAnalysisService(
        brsapi_query_service=brsapi,
        db_session=db_session,
    )


@router.get("/market", summary="آمار صف کل بازار")
async def queue_analysis_market(
    limit: int = Query(500, ge=10, le=2000, description="تعداد نمادهای بررسی‌شده"),
    service=Depends(get_queue_analysis_service),
) -> dict[str, Any]:
    """
    آمار کلی صف‌های بازار شامل:

      - summary: تعداد و درصد صف خرید/فروش
      - signals: لیست صف‌های جدید، شکسته‌شده، سنگین
      - details: جزئیات کامل هر نماد
    """
    return await service.analyze_market(limit=limit)


@router.get("/batch", summary="تحلیل صف گروهی از نمادها")
async def queue_analysis_batch(
    symbols: str = Query(..., description="لیست نمادها جدا شده با کاما (مثلاً 'فولاد,شستا,وبملت')"),
    service=Depends(get_queue_analysis_service),
) -> list[dict[str, Any]]:
    """
    تحلیل صف برای چند نماد به صورت همزمان.

    - **symbols**: لیست نمادها جدا شده با کاما (حداکثر ۲۰ نماد)

    خروجی: آرایه‌ای از نتایج analyze_symbol برای هر نماد (همگی در دیتابیس ذخیره می‌شوند)
    """
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()][:20]
    if not symbol_list:
        return []

    results: list[dict[str, Any]] = []
    for sym in symbol_list:
        try:
            result = await service.analyze_symbol(sym)
            results.append(result)
        except Exception:
            logger.exception("Queue analysis batch failed for %s", sym)
            results.append({"symbol": sym, "error": f"تحلیل صف برای {sym} ناموفق", "queue_status": "NONE"})

    return results


@router.get("/{symbol}", summary="تحلیل صف یک نماد")
async def queue_analysis_symbol(
    symbol: str,
    service=Depends(get_queue_analysis_service),
) -> dict[str, Any]:
    """
    تحلیل کامل وضعیت صف برای یک نماد بورسی.

    - **symbol**: شناسه نماد (مثلاً "فولاد")

    خروجی شامل ۵ ویژگی صف:
      - queue_status: BUY_QUEUE / SELL_QUEUE / NONE
      - queue_volume_ratio: نسبت حجم صف (۰ تا ۱)
      - queue_days_streak: تداوم صف بر حسب روز
      - queue_type_change: نوع تغییر نسبت به روز قبل
      - distance_to_limit: فاصله تا سقف/کف دامنه

    نتیجه به صورت خودکار در جدول queue_analysis_results ذخیره می‌شود.
    """
    return await service.analyze_symbol(symbol)
