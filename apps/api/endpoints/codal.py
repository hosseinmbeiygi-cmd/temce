from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_brsapi_query_service, get_codal_service, get_db_session
from core.db_utils import safe_row_str
from core.exceptions import NotFoundError
from core.logging import get_logger
from core.result import PaginatedResult
from schemas.api.codal import CodalListResponse, CodalReportResponse, CodalSearchRequest

logger = get_logger(__name__)
from schemas.common.responses import ApiResponse
from services.codal_attachment_service import CodalAttachmentDownloadService
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
    # Handle both Disclosure domain objects and dict/ORM objects
    if isinstance(item, dict):
        return CodalReportResponse(
            id=str(item.get("id", "")),
            symbol=str(item.get("symbol", "")),
            company_name=str(item.get("company_name", "")),
            isin=str(item.get("isin", "")),
            report_type=str(item.get("report_type", "")),
            fiscal_year=str(item.get("fiscal_year", "")),
            period=str(item.get("period", "")),
            audit_status=str(item.get("audit_status", "")),
            publish_date=str(item.get("publish_date", "")),
            attachment_url=str(item.get("attachment_url", "")),
            summary={"text": str(item.get("summary", ""))} if item.get("summary") else {},
            created_at=str(item.get("created_at", "")),
        )
    # Disclosure domain object
    extra = getattr(item, "extra", {}) or {}
    pub_date = getattr(item, "publish_date", None)
    pub_date_str = ""
    if pub_date:
        pub_date_str = str(pub_date)
    elif extra.get("raw_publish_date"):
        pub_date_str = extra["raw_publish_date"]

    return CodalReportResponse(
        id=getattr(item, "id", ""),
        symbol=getattr(item, "symbol", ""),
        company_name=getattr(item, "company_name", "") or getattr(item, "instrument_id", ""),
        isin=getattr(item, "isin", ""),
        report_type=getattr(item, "report_type", "") or getattr(item, "disclosure_type", ""),
        fiscal_year=getattr(item, "fiscal_year", ""),
        period=getattr(item, "period", ""),
        audit_status=getattr(item, "audit_status", ""),
        publish_date=pub_date_str,
        attachment_url=getattr(item, "attachment_url", "") or getattr(item, "url", ""),
        summary={"text": getattr(item, "summary", "")} if getattr(item, "summary", "") else {},
        created_at=str(getattr(item, "created_at", "")) if getattr(item, "created_at", None) else "",
    )


router = APIRouter()





@router.get("")
async def list_disclosures(
    search: CodalSearchRequest = Depends(),
    service: CodalService = Depends(get_codal_service),
) -> ApiResponse[CodalListResponse]:
    try:
        # If symbol filter is provided, use get_by_symbol; otherwise list all
        if search.symbol:
            result = await service.repo.get_by_symbol(search.symbol, search.page, search.page_size)
        else:
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
        logger.exception("Codal list_disclosures failed")
        return ApiResponse[CodalListResponse](
            success=False,
            data=CodalListResponse(items=[], total=0, page=1, page_size=50),
            error={"message": "Failed to fetch Codal data — please ensure brsapi_codal_announcements table is populated"},
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
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Search codal announcements from local database."""
    conditions = []
    params: dict[str, Any] = {}

    if symbol:
        conditions.append("symbol = :symbol")
        params["symbol"] = symbol
    if date_start:
        conditions.append("publish_date >= :date_start")
        params["date_start"] = date_start
    if date_end:
        conditions.append("publish_date <= :date_end")
        params["date_end"] = date_end
    if audited == "true":
        conditions.append("audit_status = 'audited'")
    elif unaudited == "true":
        conditions.append("audit_status = 'unaudited'")

    where = " AND ".join(conditions) if conditions else "1=1"
    limit = 20
    offset = (page - 1) * limit

    try:
        # Count
        count_r = await session.execute(text(f"""
            SELECT COUNT(*) FROM codal_reports WHERE {where}
        """), params)
        total = count_r.scalar() or 0

        # Fetch page
        rows_r = await session.execute(text(f"""
            SELECT symbol, company_name, report_type, period, audit_status,
                   publish_date, summary, attachment_url
            FROM codal_reports WHERE {where}
            ORDER BY publish_date DESC
            LIMIT {limit} OFFSET {offset}
        """), params)

        announcements = []
        for row in rows_r.fetchall():
            announcements.append({
                "l18": row[0], "l30": safe_row_str(row, idx=1),
                "title": safe_row_str(row, idx=6) or safe_row_str(row, idx=2),
                "code": safe_row_str(row, idx=2),
                "date_title": safe_row_str(row, idx=5),
                "date_send": safe_row_str(row, idx=5),
                "time_send": "",
                "date_publish": safe_row_str(row, idx=5),
                "time_publish": "",
                "link": safe_row_str(row, idx=7),
                "link_pdf": "",
                "link_excel": "",
                "link_attachment": safe_row_str(row, idx=7),
                "audit_status": safe_row_str(row, idx=4),
            })

        return ApiResponse[dict[str, Any]](success=True, data={
            "count_announcement": total,
            "count_page": (total + limit - 1) // limit,
            "announcement": announcements,
        })
    except Exception as exc:
        logger.exception("Codal search failed")
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
        estimated_total = page * page_size + 1 if has_next else (page - 1) * page_size + len(page_items)
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
        logger.exception("Announcements search failed")
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult(items=[], total=0, page=1, page_size=page_size, total_pages=1),
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
        logger.exception("Failed to fetch enriched detail for %s", code)
        pass
    # No real snapshot data — do not return fabricated company profiles.
    raise NotFoundError(entity="Company", identifier=code)


@router.get("/{code}/financials")
async def financial_reports(
    code: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """سود و زیان فصلی واقعی از جدول codal_financial_statements (در صورت موجود بودن)."""
    try:
        from sqlalchemy import select

        from models.codal_financial import CodalFinancialStatementModel

        rows = (
            await session.execute(
                select(CodalFinancialStatementModel)
                .where(CodalFinancialStatementModel.symbol == code)
                .order_by(CodalFinancialStatementModel.report_date.desc())
                .limit(8)
            )
        ).scalars().all()

        quarters: list[dict[str, Any]] = []
        for r in rows:
            pd = r.parsed_data or {}
            # extract key P&L items from parsed Excel data (Persian labels)
            def _get(data: dict[str, Any], *labels: str) -> float:
                for lbl in labels:
                    if lbl in data and data[lbl] is not None:
                        try:
                            return float(data[lbl])
                        except (TypeError, ValueError):
                            continue
                return 0.0

            quarters.append({
                "period": str(r.report_date or r.report_type or ""),
                "report_type": r.report_type or "",
                "revenue": _get(pd, "فروش", "درآمد فروش", "درآمد عملیاتی"),
                "cost": _get(pd, "بهای تمام شده", "بهای تمام شده کالای فروش رفته"),
                "gross_profit": _get(pd, "سود ناخالص", "سود (زیان) ناخالص"),
                "operating_profit": _get(pd, "سود عملیاتی", "سود (زیان) عملیاتی"),
                "net_profit": _get(pd, "سود خالص", "سود (زیان) خالص", "سود (زیان) ویژه"),
                "eps": _get(pd, "سود هر سهم", "سود (زیان) هر سهم"),
            })

        return ApiResponse[dict[str, Any]](success=True, data={"symbol": code, "quarters": quarters})
    except Exception:
        logger.exception("Failed to load real financials for %s", code)
        return ApiResponse[dict[str, Any]](success=True, data={"symbol": code, "quarters": []})


@router.get("/{code}/dividends")
async def dividend_history(
    code: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """سود تقسیمی واقعی از جدول corporate_actions (در صورت موجود بودن)."""
    try:
        from sqlalchemy import select

        from models.option import CorporateActionModel

        rows = (
            await session.execute(
                select(CorporateActionModel)
                .where(
                    CorporateActionModel.symbol == code,
                    CorporateActionModel.action_type == "dividend",
                )
                .order_by(CorporateActionModel.ex_date.desc())
                .limit(20)
            )
        ).scalars().all()

        dividends = []
        for r in rows:
            params = r.params or {}
            cps = params.get("dividend") if isinstance(params, dict) else None
            dividends.append({
                "date": str(r.ex_date) if r.ex_date else "",
                "cash_per_share": float(cps or 0),
                "total_payout": float(cps or 0) * 0,  # shares unknown here — left 0
                "type": "نقدی",
                "meeting": str(r.raw_text or "")[:80],
            })
        return ApiResponse[dict[str, Any]](success=True, data={"symbol": code, "dividends": dividends})
    except Exception:
        logger.exception("Failed to load dividends for %s", code)
        return ApiResponse[dict[str, Any]](success=True, data={"symbol": code, "dividends": []})


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
        logger.exception("Failed to fetch holders for %s from BrsApi", code)
        pass
    # No real shareholder data — return empty (was previously fake data).
    return ApiResponse[dict[str, Any]](success=True, data={"symbol": code, "holders": []})


@router.get("/{code}/analysis", summary="تحلیل بنیادی نماد (داده واقعی)")
async def codal_analysis(
    code: str,
    brsapi=Depends(get_brsapi_query_service),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """تحلیل بنیادی کامل برای صفحه تحلیل کدال — داده واقعی از اسنپ‌شات،
    سهامداران، اطلاعیه‌ها و خلاصه حسابرسی کدال."""
    snap = await brsapi.get_enriched_symbol_detail(code)
    if not snap:
        snap = await brsapi.get_symbol_snapshot(code)

    holders = await brsapi.get_shareholders(code) or []
    announcements = await brsapi.get_recent_announcements(symbol=code, limit=8) or []

    # Real fundamental ratios from codal_audit_summary
    audit: dict[str, Any] = {}
    try:
        from sqlalchemy import select

        from models.codal import CodalAuditSummaryModel

        row = (
            await session.execute(
                select(CodalAuditSummaryModel).where(CodalAuditSummaryModel.symbol == code)
            )
        ).scalars().first()
        if row:
            audit = {
                "roe_pct": (row.roe or 0) * 100 if row.roe else 0,
                "roa_pct": (row.roa or 0) * 100 if row.roa else 0,
                "net_margin_pct": (row.net_margin or 0) * 100 if row.net_margin else 0,
                "debt_to_equity": row.debt_to_equity or 0,
                "current_ratio": row.current_ratio or 0,
                "health_score": row.health_score or 0,
                "revenue": row.revenue or 0,
                "net_profit": row.net_profit or 0,
            }
    except Exception:
        logger.debug("Codal audit summary unavailable for %s", code)

    price_last = snap.get("price_last") or snap.get("price_close") or 0
    price_close = snap.get("price_close") or price_last
    price_yesterday = snap.get("price_yesterday") or 0
    change = (price_last or 0) - price_yesterday
    change_pct = (change / price_yesterday * 100) if price_yesterday else 0

    eps = snap.get("eps") or 0
    shares_count = snap.get("shares_count") or 0
    market_cap = snap.get("market_value") or 0
    pe_ratio = snap.get("pe_ratio") or 0
    group_pe = snap.get("group_pe_ratio") or 0
    ps_ratio = snap.get("ps_ratio") or 0
    revenue_est = snap.get("estimated_revenue") or audit.get("revenue") or 0
    net_profit_est = snap.get("estimated_net_profit") or (eps * shares_count if shares_count else 0)

    buy_real = snap.get("buy_real_volume") or 0
    sell_real = snap.get("sell_real_volume") or 0
    buy_legal = snap.get("buy_legal_volume") or 0
    sell_legal = snap.get("sell_legal_volume") or 0
    real_net = buy_real - sell_real
    legal_net = buy_legal - sell_legal
    total_rl = buy_real + sell_real + buy_legal + sell_legal
    real_buy_pct = (buy_real / total_rl * 100) if total_rl else 0
    real_net_pct = (real_net / total_rl * 100) if total_rl else 0

    legal_count = sum(1 for h in holders if (h.get("percent") or 0) > 1)
    real_count = max(0, len(holders) - legal_count)
    top_pct = max((h.get("percent") or 0) for h in holders) if holders else 0

    price_vs_low_pct = (
        ((price_last - (snap.get("price_min") or 0)) / max((snap.get("price_max") or price_last) - (snap.get("price_min") or 0), 1) * 100)
        if price_last else 0
    )
    volume_vs_base = (snap.get("trade_volume") or 0) / max(snap.get("base_volume") or 1, 1)

    return ApiResponse[dict[str, Any]](
        success=True,
        data={
            "symbol": code,
            "company_name": snap.get("name") or f"شرکت {code}",
            "industry": snap.get("sector") or "سایر",
            "sub_sector": snap.get("sub_sector") or "",
            "market": snap.get("market") or "",
            "board": snap.get("board") or "",
            "state": snap.get("state") or "",
            "price": {
                "last": price_last,
                "yesterday": price_yesterday,
                "close": price_close,
                "min": snap.get("price_min") or 0,
                "max": snap.get("price_max") or price_last,
                "lowest_allowed": snap.get("price_lowest_allowed") or 0,
                "highest_allowed": snap.get("price_highest_allowed") or 0,
                "change": change,
                "change_pct": round(change_pct, 2),
            },
            "fundamental": {
                "eps": eps,
                "pe_ratio": pe_ratio,
                "group_pe": group_pe,
                "ps_ratio": ps_ratio,
                "market_cap": market_cap,
                "shares_count": shares_count,
                "free_float_pct": snap.get("free_float_pct") or 0,
                "base_volume": snap.get("base_volume") or 0,
                "estimated_revenue": revenue_est,
                "estimated_net_profit": net_profit_est,
                "pb_ratio": snap.get("pb_ratio") or 0,
                "roe_pct": audit.get("roe_pct") or 0,
                "roa_pct": audit.get("roa_pct") or 0,
                "dividend_yield_pct": snap.get("dividend_yield_pct") or 0,
            },
            "trade": {
                "volume": snap.get("trade_volume") or 0,
                "value": snap.get("trade_value") or 0,
                "count": snap.get("trade_count") or 0,
            },
            "real_legal": {
                "buy_real_volume": buy_real,
                "sell_real_volume": sell_real,
                "buy_legal_volume": buy_legal,
                "sell_legal_volume": sell_legal,
                "real_net": real_net,
                "legal_net": legal_net,
                "real_net_pct_of_total": round(real_net_pct, 2),
                "real_buy_pct": round(real_buy_pct, 2),
            },
            "holders": {
                "total_count": len(holders),
                "top_holder_pct": top_pct,
                "legal_holder_count": legal_count,
                "real_holder_count": real_count,
                "top_holders": [
                    {
                        "name": h.get("shareholder_name") or "نامشخص",
                        "shares": h.get("volume") or 0,
                        "percentage": h.get("percent") or 0,
                        "type": "حقوقی" if (h.get("percent") or 0) > 1 else "حقیقی",
                    }
                    for h in holders[:10]
                ],
            },
            "announcements": [
                {
                    "title": a.get("title") or "",
                    "date_publish": a.get("date_publish") or "",
                    "link_pdf": a.get("link_pdf") or "",
                    "audit_status": a.get("audit_status") or "",
                }
                for a in announcements
            ],
            "performance": {
                "price_change_pct": round(change_pct, 2),
                "price_vs_low_pct": round(price_vs_low_pct, 2),
                "volume_vs_base": round(volume_vs_base, 2),
            },
        },
    )


@router.post(
    "/import-bulk",
    summary="Bulk import Codal disclosures",
    description="Upload one or more Excel (.xlsx) or CSV files containing Codal disclosures. "
    "Files are processed concurrently. Existing records with the same symbol+report_type+fiscal_year+period are updated.",
)
async def bulk_import_codal(
    files: list[UploadFile] = File(..., description="Excel (.xlsx) or CSV files with Codal data"),
) -> ApiResponse[dict[str, Any]]:
    """Upload multiple Codal disclosure files and import them all."""
    from core.database import async_session_factory
    from repositories.codal_repository import CodalRepository
    from repositories.instrument_repository import InstrumentRepository
    from services.codal_import_service import CodalImportService

    # AsyncSession is not safe for concurrent use. Each file gets its own
    # session and repository/service graph, so one slow or failing import
    # cannot corrupt another file's transaction.
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

        if async_session_factory is None:
            all_errors.append(f"{file.filename}: database is not initialized")
            return

        async with async_session_factory() as file_session:
            codal_repo = CodalRepository(session=file_session)
            instrument_repo = InstrumentRepository(session=file_session)
            service = CodalImportService(codal_repo=codal_repo, instrument_repo=instrument_repo)
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

    results = await asyncio.gather(
        *[limited(f) for f in files],
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            logger.error("Codal file import task failed: %s", result)
            all_errors.append(f"unexpected import error: {result}")

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
    """معاملات داخلی — داده واقعی هنوز جمع‌آوری نشده؛ لیست خالی برمی‌گردد.

    (قبلاً داده ساختگی برمی‌گرداند که گمراه‌کننده بود.)
    """
    return ApiResponse[dict[str, Any]](success=True, data={"symbol": code, "trades": []})


@router.get("/announcements/{announcement_id}/attachments")
async def list_announcement_attachments(
    announcement_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[dict[str, Any]]]:
    """List downloaded/stored attachments for a Codal announcement."""
    from sqlalchemy import select

    from brsapi.models.codal import CodalAttachmentModel

    rows = await session.execute(
        select(CodalAttachmentModel).where(CodalAttachmentModel.announcement_id == announcement_id)
    )
    items = []
    for row in rows.scalars().all():
        items.append(
            {
                "id": row.id,
                "announcement_id": row.announcement_id,
                "symbol": row.symbol,
                "code": row.code,
                "attachment_type": row.attachment_type,
                "source_url": row.source_url,
                "storage_type": row.storage_type,
                "storage_path": row.storage_path,
                "file_size": row.file_size,
                "mime_type": row.mime_type,
                "status": row.status,
                "error_message": row.error_message,
                "downloaded_at": row.downloaded_at.isoformat() if row.downloaded_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return ApiResponse[list[dict[str, Any]]](success=True, data=items)


@router.get("/announcements/{announcement_id}/attachments/{attachment_type}/download")
async def download_announcement_attachment(
    announcement_id: int,
    attachment_type: str,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Download a stored Codal attachment (pdf/excel/attachment/html)."""
    from sqlalchemy import select

    from brsapi.models.codal import CodalAttachmentModel

    row = (
        await session.execute(
            select(CodalAttachmentModel).where(
                CodalAttachmentModel.announcement_id == announcement_id,
                CodalAttachmentModel.attachment_type == attachment_type,
            )
        )
    ).scalar_one_or_none()

    if not row:
        raise NotFoundError(
            entity="CodalAttachment",
            identifier=f"{announcement_id}/{attachment_type}",
        )

    if row.status != "done":
        raise NotFoundError(
            entity="CodalAttachment",
            identifier=f"{announcement_id}/{attachment_type}",
        )

    service = CodalAttachmentDownloadService(session, storage_type=row.storage_type)

    # Local storage streams from disk; S3 reads the object into memory. Both
    # paths are exposed as an async iterator so StreamingResponse stays uniform.
    async def _stream():
        async for chunk in await service.get_attachment_stream(row):
            yield chunk

    content_iterator = _stream()

    filename = f"{row.symbol or 'codal'}_{row.code or announcement_id}_{attachment_type}"
    if row.mime_type == "application/pdf":
        filename += ".pdf"
    elif row.mime_type and "excel" in row.mime_type:
        filename += ".xlsx"
    elif row.mime_type == "text/html":
        filename += ".html"
    else:
        filename += ".bin"

    return StreamingResponse(
        content_iterator,
        media_type=row.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Dynamic single-segment routes (kept LAST so they never shadow the static
#    routes above: /brsapi-search, /announcements, /import-bulk, ...) ─────────


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
