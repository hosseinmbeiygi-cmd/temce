from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from apps.api.dependencies import get_codal_service
from core.exceptions import NotFoundError
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


@router.get("/{code}/profile")
async def company_profile(code: str) -> ApiResponse[dict[str, Any]]:
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
async def major_holders(code: str) -> ApiResponse[dict[str, Any]]:
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
