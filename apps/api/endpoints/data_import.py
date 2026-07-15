from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.logging import get_logger
from schemas.common.responses import ApiResponse

logger = get_logger(__name__)

router = APIRouter()

IMPORT_HISTORY_QUERY = """
    SELECT id, job_type, status, started_at, completed_at, duration_seconds, error_message, params
    FROM job_runs
    WHERE job_type LIKE '%import%' OR job_type LIKE '%ingest%' OR job_type LIKE '%sync%'
    ORDER BY created_at DESC
    LIMIT 50
"""


@router.get("/history", summary="Import history", description="Recent import/sync job history from job_runs")
async def get_import_history(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse[dict[str, Any]]:
    try:
        r = await session.execute(text(IMPORT_HISTORY_QUERY))
        jobs: list[dict[str, Any]] = []
        for row in r.fetchall():
            jobs.append({
                "id": row[0] or "",
                "job_type": row[1] or "",
                "status": row[2] or "unknown",
                "started_at": row[3].isoformat() if row[3] else None,
                "completed_at": row[4].isoformat() if row[4] else None,
                "duration_seconds": row[5] or 0,
                "error_message": row[6][:200] if row[6] else None,
            })

        return ApiResponse[dict[str, Any]](success=True, data={
            "items": jobs,
            "total": len(jobs),
        })
    except Exception:
        logger.exception("Failed to fetch import history")
        return ApiResponse[dict[str, Any]](
            success=True,
            data={"items": [], "total": 0},
        )


INSTRUMENT_SCHEMA_HINTS = [
    {"column": "symbol", "type": "string", "required": True, "desc": "نماد سهام (مثلاً فولاد)"},
    {"column": "name", "type": "string", "required": False, "desc": "نام شرکت"},
    {"column": "isin", "type": "string", "required": False, "desc": "کد ISIN"},
    {"column": "market_type", "type": "string", "required": False, "desc": "bours | ifb | otc | base | energy"},
    {"column": "sector_code", "type": "number", "required": False, "desc": "کد صنعت"},
    {"column": "group_code", "type": "number", "required": False, "desc": "کد گروه"},
    {"column": "tick_size", "type": "number", "required": False, "desc": "اندازه حداقل تغییر قیمت"},
    {"column": "lot_size", "type": "number", "required": False, "desc": "اندازه هر لات"},
    {"column": "par_value", "type": "number", "required": False, "desc": "ارزش اسمی"},
]

QUOTE_SCHEMA_HINTS = [
    {"column": "تاریخ", "type": "string (YYYY-MM-DD)", "required": True, "desc": "تاریخ معامله"},
    {"column": "باز", "type": "number", "required": False, "desc": "قیمت باز شدن"},
    {"column": "بالا", "type": "number", "required": False, "desc": "بالاترین قیمت"},
    {"column": "پایین", "type": "number", "required": False, "desc": "پایین‌ترین قیمت"},
    {"column": "بسته", "type": "number", "required": False, "desc": "قیمت پایانی"},
    {"column": "آخرین", "type": "number", "required": False, "desc": "آخرین قیمت معامله"},
    {"column": "حجم", "type": "number", "required": False, "desc": "حجم معاملات"},
    {"column": "ارزش", "type": "number", "required": False, "desc": "ارزش معاملات"},
    {"column": "تعداد", "type": "number", "required": False, "desc": "تعداد معاملات"},
]

CODAL_SCHEMA_HINTS = [
    {"column": "symbol", "type": "string", "required": True, "desc": "نماد سهام"},
    {"column": "report_type", "type": "string", "required": True, "desc": "نوع گزارش (annual, quarterly, …)"},
    {"column": "fiscal_year", "type": "string", "required": True, "desc": "سال مالی"},
    {"column": "period", "type": "string", "required": True, "desc": "دوره (12ماهه, 3ماهه, …)"},
    {"column": "publish_date", "type": "date", "required": False, "desc": "تاریخ انتشار"},
    {"column": "summary", "type": "text", "required": False, "desc": "خلاصه گزارش"},
    {"column": "url", "type": "string", "required": False, "desc": "لینک پیوست"},
]


@router.get("/templates", summary="Import schema templates", description="Column schemas for each import type")
async def get_import_templates() -> ApiResponse[dict[str, Any]]:
    return ApiResponse[dict[str, Any]](success=True, data={
        "instruments": {
            "label": "نمادها (Instruments)",
            "endpoint": "/instruments/import",
            "method": "POST",
            "accept": ".csv, .json, .xlsx",
            "max_size_mb": 10,
            "columns": INSTRUMENT_SCHEMA_HINTS,
            "sample_endpoint": "/instruments/sample",
            "sample_label": "دانلود نمونه CSV",
        },
        "quotes": {
            "label": "قیمت‌های روزانه (Quotes)",
            "endpoint": "/quotes/import-bulk",
            "method": "POST",
            "accept": ".csv",
            "max_size_mb": 50,
            "columns": QUOTE_SCHEMA_HINTS,
            "sample_endpoint": None,
            "note": "نام فایل باید نماد باشد (مثلاً فولاد.csv). پشتیبانی از فرمت انگلیسی (TICKER, DTYYYYMMDD, ...)",
        },
        "codal": {
            "label": "اطلاعیه‌های کدال",
            "endpoint": "/codal/import-bulk",
            "method": "POST",
            "accept": ".xlsx, .csv",
            "max_size_mb": 20,
            "columns": CODAL_SCHEMA_HINTS,
            "sample_endpoint": None,
        },
    })
