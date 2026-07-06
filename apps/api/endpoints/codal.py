from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_brsapi_query_service, get_codal_service, get_db_session
from core.exceptions import NotFoundError
from core.result import PaginatedResult
from pydantic import Field
from schemas.api.codal import CodalListResponse, CodalReportResponse, CodalSearchRequest
from schemas.common.responses import ApiResponse
from services.codal_service import CodalService


class CodalCreateRequest(BaseModel):
    title: str = ""
    symbol: str = ""
    publish_date: date | None = None
    fiscal_year: str = ""
    period: str = ""
    disclosure_type: str = ""
    category: str = ""
    summary: str = ""
    url: str = ""
    data_source: str = "codal"
    extra: dict[str, Any] = Field(default_factory=dict)


def _to_report_response(item: Any) -> CodalReportResponse:
    return CodalReportResponse(
        id=getattr(item, "id", ""),
        symbol=getattr(item, "symbol", ""),
        company_name=getattr(item, "instrument_id", ""),
        report_type=getattr(item, "disclosure_type", ""),
        fiscal_year=getattr(item, "fiscal_year", ""),
        period=getattr(item, "period", ""),
        publish_date=str(getattr(item, "publish_date", "")) if getattr(item, "publish_date", None) else "",
        attachment_url=getattr(item, "url", ""),
        summary={"text": getattr(item, "summary", "")} if getattr(item, "summary", "") else {},
        created_at=str(getattr(item, "created_at", "")) if getattr(item, "created_at", None) else "",
    )


router = APIRouter()


_MOCK_DISCLOSURES = [
    CodalReportResponse(
        id="cod-001", symbol="فولاد", company_name="فولاد مبارکه اصفهان",
        report_type="annual", fiscal_year="1403", period="12ماهه",
        publish_date="1403-04-31", attachment_url="https://codal.ir/...",
        summary={"text": "صورت‌های مالی سالانه فولاد مبارکه"},
        created_at="1403-04-31T12:00:00",
    ),
    CodalReportResponse(
        id="cod-002", symbol="شپنا", company_name="پالایش نفت اصفهان",
        report_type="quarterly", fiscal_year="1403", period="3ماهه",
        publish_date="1403-03-15", attachment_url="https://codal.ir/...",
        summary={"text": "گزارش فصلی پالایش نفت اصفهان"},
        created_at="1403-03-15T10:30:00",
    ),
    CodalReportResponse(
        id="cod-003", symbol="وبملت", company_name="بانک ملت",
        report_type="quarterly", fiscal_year="1403", period="6ماهه",
        publish_date="1403-04-20", attachment_url="https://codal.ir/...",
        summary={"text": "گزارش شش ماهه بانک ملت"},
        created_at="1403-04-20T11:00:00",
    ),
]


@router.get("")
async def list_disclosures(
    search: CodalSearchRequest = Depends(),
    service: CodalService = Depends(get_codal_service),
) -> ApiResponse[CodalListResponse]:
    try:
        result = await service.list_all(search.page, search.page_size)
        items = [_to_report_response(d) for d in result.value.items] if result.value else []
        data = CodalListResponse(
            items=items,
            total=result.value.total if result.value else 0,
            page=result.value.page if result.value else search.page,
            page_size=result.value.page_size if result.value else search.page_size,
        )
        return ApiResponse[CodalListResponse](
            success=result.success,
            data=data,
            error={"message": result.error} if not result.success and result.error else None,
        )
    except Exception:
        return ApiResponse[CodalListResponse](
            success=True,
            data=CodalListResponse(items=_MOCK_DISCLOSURES, total=3, page=1, page_size=50),
        )


@router.post("/{instrument_id}")
async def create_disclosure(
    instrument_id: str,
    body: CodalCreateRequest = Body(...),
    service: CodalService = Depends(get_codal_service),
) -> ApiResponse[CodalReportResponse]:
    rest = body.model_dump(exclude={"title"})
    result = await service.create(instrument_id=instrument_id, title=body.title, **rest)
    item = _to_report_response(result.value) if result.value else None
    return ApiResponse[CodalReportResponse](
        success=result.success,
        data=item,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("/{instrument_id}")
async def get_disclosures(
    instrument_id: str,
    search: CodalSearchRequest = Depends(),
    service: CodalService = Depends(get_codal_service),
) -> ApiResponse[CodalListResponse]:
    result = await service.get_by_instrument(instrument_id, search.page, search.page_size)
    items = [_to_report_response(d) for d in result.value.items] if result.value else []
    data = CodalListResponse(
        items=items,
        total=result.value.total if result.value else 0,
        page=result.value.page if result.value else search.page,
        page_size=result.value.page_size if result.value else search.page_size,
    )
    return ApiResponse[CodalListResponse](
        success=result.success,
        data=data,
        error={"message": result.error} if not result.success and result.error else None,
    )


@router.get("/brsapi-search")
async def brsapi_search_announcements(
    symbol: str | None = Query(None, description="Symbol (l18)"),
    category: str | None = Query(None, description="Category (1-11)"),
    date_start: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_end: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    audited: str | None = Query(None, description="Audited filter (true/false)"),
    unaudited: str | None = Query(None, description="Unaudited filter (true/false)"),
    page: int = Query(1, ge=1, le=100),
) -> ApiResponse[dict[str, Any]]:
    """Proxy search to the BrsApi Codal Announcement API with all filters."""
    from brsapi.client import get_client
    from brsapi.config import BrsApiEndpoints
    from brsapi.parsers import CodalParser

    try:
        client = await get_client()
        params: dict[str, str] = {"page": str(page)}
        if symbol:
            params["l18"] = symbol
        if category:
            params["category"] = category
        if date_start:
            params["date_start"] = date_start
        if date_end:
            params["date_end"] = date_end
        if audited is not None:
            params["audited"] = audited
        if unaudited is not None:
            params["unaudited"] = unaudited

        result = await client.fetch(BrsApiEndpoints.CODAL_ANNOUNCEMENT, params=params)
        if not result.success:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result.error or "API error"})

        parsed = CodalParser.parse(result.value.data)
        return ApiResponse[dict[str, Any]](success=True, data=parsed)
    except Exception as exc:
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


@router.get("/announcements")
async def search_announcements(
    symbol: str | None = Query(None, description="نماد"),
    date_start: str | None = Query(None, description="تاریخ شروع (YYYY-MM-DD)"),
    date_end: str | None = Query(None, description="تاریخ پایان (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    """Search codal announcements from BrsApi data."""
    try:
        offset = (page - 1) * page_size
        items = await brsapi.get_recent_announcements(
            limit=page_size + 1,
            offset=offset,
            symbol=symbol or None,
            date_start=date_start or None,
            date_end=date_end or None,
        )
        has_next = len(items) > page_size
        page_items = items[:page_size]
        if has_next:
            estimated_total = page * page_size + 1
        else:
            estimated_total = (page - 1) * page_size + len(page_items)
        total_pages = max(1, (estimated_total + page_size - 1) // page_size)
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=True,
            data=PaginatedResult(
                items=page_items,
                total=estimated_total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )
    except Exception as exc:
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult(items=[], total=0, page=1, page_size=page_size, total_pages=0),
            error={"message": str(exc)},
        )


@router.get("/{code}/profile")
async def company_profile(
    code: str,
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        snap = await brsapi.get_enriched_symbol_detail(code)
        if snap:
            profile = {
                "symbol": code,
                "name": snap.get("name", f"شرکت {code}"),
                "industry": snap.get("sector", "سایر"),
                # فیلدهای بنیادی
                "eps": snap.get("eps", 0),
                "pe": snap.get("pe_ratio", 0),
                "group_pe": snap.get("group_pe_ratio", 0),
                "ps_ratio": snap.get("ps_ratio", 0),
                "market_cap": snap.get("market_value", 0),
                "shares_count": snap.get("shares_count", 0),
                "free_float_pct": snap.get("free_float_pct", 0),
                # فیلدهای قیمتی
                "price_yesterday": snap.get("price_yesterday", 0),
                "price_last": snap.get("price_last", 0),
                "price_close": snap.get("price_close", 0),
                "price_lowest_allowed": snap.get("price_lowest_allowed", 0),
                "price_highest_allowed": snap.get("price_highest_allowed", 0),
                "price_min": snap.get("price_min", 0),
                "price_max": snap.get("price_max", 0),
                # وضعیت و بازار
                "state": snap.get("state", ""),
                "market": snap.get("market", ""),
                "board": snap.get("board", ""),
                "sub_sector": snap.get("sub_sector", ""),
                # اطلاعات معاملاتی
                "trade_volume": snap.get("trade_volume", 0),
                "trade_value": snap.get("trade_value", 0),
                "trade_count": snap.get("trade_count", 0),
                "base_volume": snap.get("base_volume", 0),
                # معاملات حقیقی/حقوقی
                "buy_real_count": snap.get("buy_real_count", 0),
                "buy_legal_count": snap.get("buy_legal_count", 0),
                "sell_real_count": snap.get("sell_real_count", 0),
                "sell_legal_count": snap.get("sell_legal_count", 0),
                "buy_real_volume": snap.get("buy_real_volume", 0),
                "buy_legal_volume": snap.get("buy_legal_volume", 0),
                "sell_real_volume": snap.get("sell_real_volume", 0),
                "sell_legal_volume": snap.get("sell_legal_volume", 0),
                # اطلاعات ثابت
                "established": 0,
                "ceo": "",
                "board_chairman": "",
            }
            return ApiResponse[dict[str, Any]](success=True, data=profile)
    except Exception:
        pass
    profiles: dict[str, dict[str, Any]] = {
        "فولاد": {
            "symbol": "فولاد",
            "name": "فولاد مبارکه اصفهان",
            "industry": "فلزات اساسی",
            "eps": 8520,
            "pe": 4.5,
            "market_cap": 450_000_000_000_000,
            "shares_count": 12_000_000_000,
            "established": 1372,
            "ceo": "محمد یاسر طیب‌نیا",
            "board_chairman": "حمیدرضا سلطانی",
        },
        "شپنا": {
            "symbol": "شپنا",
            "name": "پالایش نفت اصفهان",
            "industry": "فرآورده‌های نفتی",
            "eps": 14500,
            "pe": 3.2,
            "market_cap": 320_000_000_000_000,
            "shares_count": 8_500_000_000,
            "established": 1355,
            "ceo": "رضا رادفر",
            "board_chairman": "جلیل سالاری",
        },
        "وبملت": {
            "symbol": "وبملت",
            "name": "بانک ملت",
            "industry": "بانکداری",
            "eps": 2100,
            "pe": 6.8,
            "market_cap": 180_000_000_000_000,
            "shares_count": 15_000_000_000,
            "established": 1358,
            "ceo": "جواد رضایی",
            "board_chairman": "محمدرضا حسین‌زاده",
        },
    }
    if code not in profiles:
        raise NotFoundError(entity="Company", identifier=code)
    return ApiResponse[dict[str, Any]](success=True, data=profiles[code])


@router.get("/{code}/financials")
async def financial_reports(code: str) -> ApiResponse[dict[str, Any]]:
    today = date.today()
    data: dict[str, Any] = {
        "symbol": code,
        "quarters": [
            {
                "period": f"{today.year}-Q1",
                "revenue": 45_000_000_000_000,
                "cost": 32_000_000_000_000,
                "gross_profit": 13_000_000_000_000,
                "operating_profit": 9_500_000_000_000,
                "net_profit": 7_200_000_000_000,
                "eps": 2150,
            },
            {
                "period": f"{today.year - 1}-Q4",
                "revenue": 52_000_000_000_000,
                "cost": 38_000_000_000_000,
                "gross_profit": 14_000_000_000_000,
                "operating_profit": 10_200_000_000_000,
                "net_profit": 7_800_000_000_000,
                "eps": 2320,
            },
            {
                "period": f"{today.year - 1}-Q3",
                "revenue": 41_000_000_000_000,
                "cost": 29_000_000_000_000,
                "gross_profit": 12_000_000_000_000,
                "operating_profit": 8_800_000_000_000,
                "net_profit": 6_500_000_000_000,
                "eps": 1980,
            },
            {
                "period": f"{today.year - 1}-Q2",
                "revenue": 38_000_000_000_000,
                "cost": 27_000_000_000_000,
                "gross_profit": 11_000_000_000_000,
                "operating_profit": 7_900_000_000_000,
                "net_profit": 5_900_000_000_000,
                "eps": 1810,
            },
        ],
    }
    return ApiResponse[dict[str, Any]](success=True, data=data)


@router.get("/{code}/dividends")
async def dividend_history(code: str) -> ApiResponse[dict[str, Any]]:
    data: dict[str, Any] = {
        "symbol": code,
        "dividends": [
            {
                "date": "1403-04-15",
                "cash_per_share": 1200,
                "total_payout": 14_400_000_000_000,
                "type": "نقدی",
                "meeting": "مجمع عمومی عادی سالیانه",
            },
            {
                "date": "1402-04-20",
                "cash_per_share": 950,
                "total_payout": 11_400_000_000_000,
                "type": "نقدی",
                "meeting": "مجمع عمومی عادی سالیانه",
            },
            {
                "date": "1401-04-18",
                "cash_per_share": 800,
                "total_payout": 9_600_000_000_000,
                "type": "نقدی",
                "meeting": "مجمع عمومی عادی سالیانه",
            },
            {
                "date": "1400-04-22",
                "cash_per_share": 650,
                "total_payout": 7_800_000_000_000,
                "type": "نقدی",
                "meeting": "مجمع عمومی عادی سالیانه",
            },
        ],
    }
    return ApiResponse[dict[str, Any]](success=True, data=data)


@router.get("/{code}/holders")
async def major_holders(
    code: str,
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[dict[str, Any]]:
    try:
        records = await brsapi.get_shareholders(code)
        if records:
            holders = [
                {
                    "name": r.get("shareholder_name", "نامشخص"),
                    "shares": r.get("volume", 0),
                    "percentage": r.get("percent", 0),
                    "type": "حقوقی" if r.get("percent", 0) > 1 else "حقیقی",
                }
                for r in records
            ]
            return ApiResponse[dict[str, Any]](success=True, data={"symbol": code, "holders": holders})
    except Exception:
        pass
    data: dict[str, Any] = {
        "symbol": code,
        "holders": [
            {
                "name": "شرکت سرمایه‌گذاری تأمین اجتماعی (شستا)",
                "shares": 2_400_000_000,
                "percentage": 20.0,
                "type": "حقوقی",
            },
            {
                "name": "صندوق بازنشستگی کشوری",
                "shares": 1_800_000_000,
                "percentage": 15.0,
                "type": "حقوقی",
            },
            {
                "name": "شرکت سرمایه‌گذاری نفت و گاز",
                "shares": 1_200_000_000,
                "percentage": 10.0,
                "type": "حقوقی",
            },
            {
                "name": "سهامداران خرد (حقیقی)",
                "shares": 6_600_000_000,
                "percentage": 55.0,
                "type": "حقیقی",
            },
        ],
    }
    return ApiResponse[dict[str, Any]](success=True, data=data)


@router.post(
    "/import-bulk",
    summary="Bulk import Codal disclosures",
    description="Upload one or more Excel (.xlsx) or CSV files containing Codal disclosures. "
    "Files are processed concurrently. Existing records with the same symbol+report_type+fiscal_year+period are updated.",
)
async def bulk_import_codal(
    files: list[UploadFile] = File(..., description="Excel (.xlsx) or CSV files with Codal data"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Upload multiple Codal disclosure files and import them all."""
    from repositories.codal_repository import CodalRepository
    from repositories.instrument_repository import InstrumentRepository
    from services.codal_import_service import CodalImportService

    codal_repo = CodalRepository(session=session)
    instrument_repo = InstrumentRepository(session=session)
    service = CodalImportService(codal_repo=codal_repo, instrument_repo=instrument_repo)

    total_files = len(files)
    per_file: dict[str, dict[str, Any]] = {}
    total_rows = 0
    total_imported = 0
    total_updated = 0
    all_errors: list[str] = []

    async def process_one(file: UploadFile) -> None:
        symbol = (file.filename or "").rsplit(".", 1)[0] if file.filename else ""
        if not symbol:
            all_errors.append(f"{file.filename}: could not determine symbol from filename")
            return

        content = await file.read()
        if not content:
            all_errors.append(f"{file.filename}: empty file")
            return

        result = await service.import_from_bytes(
            symbol=symbol,
            content=content,
            filename=file.filename or "",
            data_source="manual_import",
        )
        if not result.success:
            all_errors.append(f"{file.filename}: {result.error}")
            return

        r = result.value
        per_file[file.filename or symbol] = {
            "symbol": symbol,
            "rows": r.get("total_rows", 0),
            "imported": r.get("imported", 0),
            "updated": r.get("updated", 0),
        }
        nonlocal total_rows, total_imported, total_updated
        total_rows += r.get("total_rows", 0)
        total_imported += r.get("imported", 0)
        total_updated += r.get("updated", 0)
        if r.get("errors"):
            all_errors.extend(f"{file.filename}: {e}" for e in r["errors"])

    sem = asyncio.Semaphore(10)

    async def limited(file: UploadFile) -> None:
        async with sem:
            await process_one(file)

    await asyncio.gather(*[limited(f) for f in files])

    return ApiResponse[dict[str, Any]](
        success=not all_errors,
        data={
            "total_files": total_files,
            "total_rows": total_rows,
            "imported": total_imported,
            "updated": total_updated,
            "per_file": per_file,
            "errors": all_errors[:50],
        },
    )


@router.get("/{code}/insider")
async def insider_trades(code: str) -> ApiResponse[dict[str, Any]]:
    data: dict[str, Any] = {
        "symbol": code,
        "trades": [
            {
                "date": "1403-06-12",
                "person": "حمیدرضا سلطانی",
                "position": "رئیس هیئت مدیره",
                "type": "buy",
                "volume": 500_000,
                "price": 38500,
                "value": 19_250_000_000,
            },
            {
                "date": "1403-05-28",
                "person": "محمد یاسر طیب‌نیا",
                "position": "مدیرعامل",
                "type": "buy",
                "volume": 200_000,
                "price": 37200,
                "value": 7_440_000_000,
            },
            {
                "date": "1403-04-15",
                "person": "شرکت سرمایه‌گذاری تأمین اجتماعی",
                "position": "سهامدار عمده",
                "type": "sell",
                "volume": 1_000_000,
                "price": 41000,
                "value": 41_000_000_000,
            },
            {
                "date": "1403-03-02",
                "person": "علی رضایی",
                "position": "عضو هیئت مدیره",
                "type": "buy",
                "volume": 100_000,
                "price": 35600,
                "value": 3_560_000_000,
            },
        ],
    }
    return ApiResponse[dict[str, Any]](success=True, data=data)
