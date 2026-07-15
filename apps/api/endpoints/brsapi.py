"""
BrsApi endpoints — commodity & cryptocurrency realtime data.

Provides read-only access to cached commodity and cryptocurrency prices
fetched from BrsApi.ir and stored in PostgreSQL.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func as sa_func
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_brsapi_query_service, get_db_session
from brsapi.services.query_service import BrsApiQueryService
from core.result import PaginatedResult
from schemas.common.responses import ApiResponse

router = APIRouter()


# ── Health ─────────────────────────────────────────────────────────


@router.get("/health", summary="BrsApi health", description="Check BrsApi integration health and connectivity")
async def brsapi_health(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[dict[str, Any]]:
    """Check connection status of the BrsApi integration."""
    try:
        stats = await service.get_brsapi_stats()
        return ApiResponse[dict[str, Any]](success=True, data={"status": "connected", **stats})
    except Exception as exc:
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"status": "error", "message": str(exc)},
        )


# ── Commodities ────────────────────────────────────────────────────


@router.get(
    "/commodities",
    summary="Global commodity prices",
    description="Realtime prices for precious metals, base metals, and energy commodities",
)
async def get_commodity_prices(
    category: str | None = Query(None, description="Filter: precious_metal | base_metal | energy"),
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return latest commodity prices, optionally filtered by category."""
    try:
        data = await service.get_commodity_prices(category=category)
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/commodities/categories",
    summary="Commodity categories",
    description="List available commodity categories with item counts",
)
async def get_commodity_categories(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return grouped commodity data by category."""
    try:
        categories = await service.get_commodity_categories()
        return ApiResponse[list[dict[str, Any]]](success=True, data=categories)
    except Exception as exc:
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


# ── Cryptocurrency ────────────────────────────────────────────────


@router.get(
    "/crypto",
    summary="Cryptocurrency prices",
    description="Realtime prices for top cryptocurrencies in USD and IRR",
)
async def get_crypto_prices(
    limit: int = Query(50, ge=1, le=200, description="Number of top coins to return"),
    sort_by: str = Query("rank", description="Sort field: rank | name | price_usd | change_percent | market_cap"),
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return latest cryptocurrency prices sorted by the given field."""
    valid_sort = {"rank", "name", "price_usd", "change_percent", "market_cap"}
    if sort_by not in valid_sort:
        sort_by = "rank"
    try:
        data = await service.get_crypto_prices(limit=limit, sort_by=sort_by)
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


@router.get(
    "/crypto/top",
    summary="Top cryptocurrencies by market cap",
    description="Top 10 cryptocurrencies by market capitalisation",
)
async def get_top_crypto(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return top 10 crypto by market cap."""
    try:
        data = await service.get_crypto_prices(limit=10, sort_by="market_cap")
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


# ── Gold & Coins ──────────────────────────────────────────────────


@router.get(
    "/gold-coin",
    summary="Gold & coin prices",
    description="Realtime gold and coin prices (18ayar, 24ayar, coin, etc.)",
)
async def get_gold_coin_prices(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return latest gold & coin prices."""
    try:
        data = await service.get_gold_coin_prices()
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


# gold-24h endpoint removed — data source no longer synced.
# Gold data is available via /gold-coin (from Gold_Currency.php combined endpoint).


# ── Currency / Forex ──────────────────────────────────────────────


@router.get(
    "/currency",
    summary="Currency / forex prices",
    description="Realtime currency exchange rates (USD, EUR, GBP, AED, etc.)",
)
async def get_currency_prices(
    service: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return latest currency/forex prices."""
    try:
        data = await service.get_currency_prices()
        return ApiResponse[list[dict[str, Any]]](success=True, data=data)
    except Exception as exc:
        return ApiResponse[list[dict[str, Any]]](success=False, data=[], error={"message": str(exc)})


# currency-24h endpoint removed — data source no longer synced.
# Currency data is available via /currency (from Gold_Currency.php combined endpoint).


# ── Historical Daily ────────────────────────────────────────────────


@router.get(
    "/history/{symbol}",
    summary="Historical daily prices",
    description="Daily OHLCV price data for a symbol from the brsapi_historical_daily or core quotes table",
)
async def get_historical_daily(
    symbol: str,
    limit: int = Query(365, ge=1, le=2000, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    date_start: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_end: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    """
    Return daily historical price data for a symbol, ordered by date descending.

    First tries the BrsApi ``brsapi_historical_daily`` table. If no data is
    found there, falls back to the core ``quotes`` table (QuoteModel) where
    imported historical data is stored.

    Supports pagination via ``limit``/``offset`` and optional date range
    filtering via ``date_start``/``date_end``.
    """
    from sqlalchemy import func as sa_func
    from sqlalchemy import select as sa_select

    from brsapi.models.tsetmc import HistoricalDailyModel

    try:
        conditions = [HistoricalDailyModel.symbol == symbol]
        if date_start:
            conditions.append(HistoricalDailyModel.date >= date_start)
        if date_end:
            conditions.append(HistoricalDailyModel.date <= date_end)

        # Try HistoricalDailyModel first
        count_stmt = sa_select(sa_func.count()).select_from(HistoricalDailyModel).where(*conditions)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        if total > 0:
            stmt = (
                sa_select(HistoricalDailyModel)
                .where(*conditions)
                .order_by(HistoricalDailyModel.date.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            items = []
            for row in rows:
                items.append({
                    "id": row.id,
                    "symbol": row.symbol,
                    "date": row.date,
                    "time": row.time,
                    "trade_count": row.trade_count,
                    "trade_volume": row.trade_volume,
                    "trade_value": row.trade_value,
                    "price_min": row.price_min,
                    "price_max": row.price_max,
                    "price_yesterday": row.price_yesterday,
                    "price_first": row.price_first,
                    "price_last": row.price_last,
                    "price_last_change": row.price_last_change,
                    "price_last_change_pct": row.price_last_change_pct,
                    "price_close": row.price_close,
                    "price_close_change": row.price_close_change,
                    "price_close_change_pct": row.price_close_change_pct,
                })

            page_size = limit if limit > 0 else 50
            page = (offset // page_size) + 1
            total_pages = max(1, (total + page_size - 1) // page_size)

            return ApiResponse[PaginatedResult[dict[str, Any]]](
                success=True,
                data=PaginatedResult[dict[str, Any]](
                    items=items,
                    total=total,
                    page=page,
                    page_size=page_size,
                    total_pages=total_pages,
                ),
            )
    except Exception:
        pass  # Fall through to quotes table

    # ── Fallback: core quotes table (QuoteModel) ──
    try:
        from models.quote import QuoteModel

        q_conditions = [QuoteModel.symbol == symbol, QuoteModel.timeframe == "1d"]
        if date_start:
            q_conditions.append(QuoteModel.date >= date_start)
        if date_end:
            q_conditions.append(QuoteModel.date <= date_end)

        # Total count
        q_count_stmt = sa_select(sa_func.count()).select_from(QuoteModel).where(*q_conditions)
        q_count_result = await session.execute(q_count_stmt)
        q_total = q_count_result.scalar() or 0

        if q_total == 0:
            return ApiResponse[PaginatedResult[dict[str, Any]]](
                success=True,
                data=PaginatedResult[dict[str, Any]](items=[], total=0, page=1, page_size=limit, total_pages=0),
            )

        q_stmt = (
            sa_select(QuoteModel)
            .where(*q_conditions)
            .order_by(QuoteModel.date.desc())
            .offset(offset)
            .limit(limit)
        )
        q_result = await session.execute(q_stmt)
        q_rows = q_result.scalars().all()

        items = []
        for row in q_rows:
            pc = row.price_close or 0
            pl = row.price_last or pc
            py = row.price_yesterday or 0
            change = pl - py
            change_pct = (change / py * 100) if py else 0
            items.append({
                "id": row.id,
                "symbol": row.symbol,
                "date": row.date,
                "time": row.time,
                "trade_count": row.trade_count,
                "trade_volume": row.volume,
                "trade_value": row.value,
                "price_min": row.price_low or row.price_min or 0,
                "price_max": row.price_high or row.price_max or 0,
                "price_yesterday": py,
                "price_first": row.price_first or row.price_open or 0,
                "price_last": pl,
                "price_last_change": row.price_change or round(change, 0),
                "price_last_change_pct": row.price_change_pct or round(change_pct, 2),
                "price_close": pc,
                "price_close_change": round(pc - py, 0),
                "price_close_change_pct": round(((pc - py) / py * 100), 2) if py else 0,
            })

        page_size = limit if limit > 0 else 50
        page = (offset // page_size) + 1
        total_pages = max(1, (q_total + page_size - 1) // page_size)

        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=True,
            data=PaginatedResult[dict[str, Any]](
                items=items,
                total=q_total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )
    except Exception as exc:
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult[dict[str, Any]](items=[], total=0, page=1, page_size=limit, total_pages=0),
            error={"message": str(exc)},
        )


# ── Codal Announcements ──────────────────────────────────────────


@router.get(
    "/codal-announcements",
    summary="Codal announcements from brsapi",
    description="Codal announcements from the brsapi_codal_announcements table with instrument_id support",
)
async def get_codal_announcements(
    symbol: str | None = Query(None, description="Filter by symbol"),
    instrument_id: str | None = Query(None, description="Filter by instrument_id"),
    date_start: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_end: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    """
    Return codal announcements from the ``brsapi_codal_announcements`` table.

    Supports filtering by ``symbol``, ``instrument_id``, and date range.
    Returns ``ins_id`` and ``instrument_id`` fields for instrument linking.
    If ``instrument_id`` is set, also returns the instrument name via JOIN.
    """
    from sqlalchemy import func as sa_func
    from sqlalchemy import select as sa_select

    from brsapi.models.codal import CodalAnnouncementModel

    try:
        conditions = []
        if symbol:
            conditions.append(CodalAnnouncementModel.symbol == symbol)
        if instrument_id:
            conditions.append(CodalAnnouncementModel.instrument_id == instrument_id)
        if date_start:
            conditions.append(CodalAnnouncementModel.date_publish >= date_start)
        if date_end:
            conditions.append(CodalAnnouncementModel.date_publish <= date_end)

        # Total count
        count_stmt = sa_select(sa_func.count()).select_from(CodalAnnouncementModel).where(*conditions)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            sa_select(CodalAnnouncementModel)
            .where(*conditions)
            .order_by(CodalAnnouncementModel.date_publish.desc().nullslast())
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        # Build a lookup for instrument names
        instrument_names: dict[str, str] = {}
        instr_ids = list({str(r.instrument_id) for r in rows if r.instrument_id})
        if instr_ids:
            from sqlalchemy import column
            from sqlalchemy import select as _s
            from sqlalchemy import text as _t
            try:
                name_result = await session.execute(
                    _s(column("id"), column("symbol").label("instr_symbol"))
                    .select_from(_t("instruments"))
                    .where(column("id").in_(instr_ids))
                )
                for nr in name_result:
                    instrument_names[str(nr.id)] = str(nr.instr_symbol)
            except Exception:
                pass

        items = []
        for row in rows:
            rid = str(row.instrument_id) if row.instrument_id else None
            items.append({
                "id": row.id,
                "symbol": row.symbol,
                "company_name": row.company_name,
                "title": row.title,
                "code": row.code,
                "date_publish": row.date_publish,
                "time_publish": row.time_publish,
                "date_title": row.date_title,
                "date_send": row.date_send,
                "time_send": row.time_send,
                "link": row.link,
                "link_pdf": row.link_pdf,
                "link_excel": row.link_excel,
                "link_attachment": row.link_attachment,
                "ins_id": row.ins_id,
                "instrument_id": rid,
                "instrument_symbol": instrument_names.get(rid) if rid else None,
                "fetched_at": row.fetched_at,
                "created_at": str(row.created_at) if row.created_at else None,
            })

        total_pages = max(1, (total + page_size - 1) // page_size)

        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=True,
            data=PaginatedResult[dict[str, Any]](
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            ),
        )
    except Exception as exc:
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult[dict[str, Any]](items=[], total=0, page=1, page_size=page_size, total_pages=0),
            error={"message": str(exc)},
        )


@router.get(
    "/codal-announcements/lazy/{symbol}",
    summary="Fetch Codal announcements on-demand for a symbol",
    description="Fetches Codal announcements from BrsApi API for a specific symbol, stores them in DB, and returns them. Uses lazy per-symbol approach.",
)
async def get_codal_announcements_lazy(
    symbol: str,
    page: int = Query(1, ge=1, le=100, description="Page number"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """
    On-demand fetch of Codal announcements for a specific symbol.

    Calls the BrsApi ``/Codal/Announcement.php`` endpoint with ``l18=symbol``,
    stores the parsed announcements in the ``brsapi_codal_announcements`` table
    (with ``ins_id`` and ``instrument_id`` populated), and returns them.

    This is the **lazy per-symbol** approach — no batch sync needed.
    """
    from sqlalchemy import select as _s

    from brsapi.client import get_client
    from brsapi.config import BrsApiEndpoints
    from brsapi.models.codal import CodalAnnouncementModel
    from brsapi.parsers import CodalParser
    from brsapi.repositories import BulkUpsertRepository

    try:
        client = await get_client()

        # 1. Fetch from BrsApi with l18 param
        result = await client.fetch(
            BrsApiEndpoints.CODAL_ANNOUNCEMENT,
            params={"l18": symbol, "page": str(page)},
        )
        if not result.success:
            return ApiResponse[dict[str, Any]](success=False, error={"message": result.error or "API fetch failed"})

        # 2. Parse announcements
        records = CodalParser.parse_announcements_only(result.value.data)

        if not records:
            return ApiResponse[dict[str, Any]](success=True, data={
                "symbol": symbol,
                "announcements": [],
                "count": 0,
                "message": "No announcements found for this symbol",
            })

        # 3. Lookup ins_id + instrument_id using SnapshotModel
        from brsapi.models import SymbolSnapshotModel

        stmt = _s(
            SymbolSnapshotModel.symbol,
            SymbolSnapshotModel.ins_id,
            SymbolSnapshotModel.instrument_id,
        ).where(SymbolSnapshotModel.symbol == symbol)
        snap_result = await session.execute(stmt)
        snap_row = snap_result.one_or_none()

        ins_id = str(snap_row.ins_id) if snap_row and snap_row.ins_id else None
        instrument_id = str(snap_row.instrument_id) if snap_row and snap_row.instrument_id else None

        # Fallback: try instruments table
        if not instrument_id:
            try:
                from sqlalchemy import column as _c
                from sqlalchemy import text as _t
                fb = await session.execute(
                    _s(_c("id")).select_from(_t("instruments")).where(_c("symbol") == symbol)
                )
                fb_row = fb.scalar_one_or_none()
                if fb_row:
                    instrument_id = str(fb_row)
            except Exception:
                pass

        # 4. Attach ins_id & instrument_id to each record
        for r in records:
            if ins_id:
                r["ins_id"] = ins_id
            if instrument_id:
                r["instrument_id"] = instrument_id

        # 5. Store in DB (retry without instrument fields if FK constraint fails)
        repo = BulkUpsertRepository(session, CodalAnnouncementModel)
        stored = 0
        try:
            stored = await repo.bulk_insert(records)
            await session.commit()
        except Exception:
            await session.rollback()
            # Retry without ins_id/instrument_id in case FK constraint fails
            for r in records:
                r.pop("ins_id", None)
                r.pop("instrument_id", None)
            try:
                stored = await repo.bulk_insert(records)
                await session.commit()
            except Exception:
                await session.rollback()
                stored = 0

        return ApiResponse[dict[str, Any]](success=True, data={
            "symbol": symbol,
            "announcements": records,
            "count": len(records),
            "stored": stored,
            "ins_id": ins_id,
            "instrument_id": instrument_id,
        })

    except Exception as exc:
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ═══════════════════════════════════════════════════════════════════
# BrsApi Management — sync, status, download
# ═══════════════════════════════════════════════════════════════════

from brsapi.client import get_client
from brsapi.config import BrsApiEndpoints
from brsapi.models import (
    CandlestickModel,
    CodalAnnouncementModel,
    CommodityPriceModel,
    CryptoPriceModel,
    CurrencyPriceModel,
    GoldCoinHistoryModel,
    GoldCoinPriceModel,
    HistoricalDailyModel,
    HistoricalRealLegalModel,
    ImeCertificateModel,
    ImeFundModel,
    ImeFutureModel,
    ImeOptionModel,
    ImePhysicalTradeModel,
    IndexValueModel,
    IntradayTradeModel,
    NavRecordModel,
    OptionSnapshotModel,
    ShareholderRecordModel,
    SymbolDetailModel,
    SymbolSnapshotModel,
)
from brsapi.parsers import (
    CodalParser,
    CommodityParser,
    CryptoParser,
    CurrencyParser,
    GoldCoinParser,
    ImeParser,
    TsetmcParser,
)
from brsapi.repositories import SyncLogRepository
from core.logging import get_logger as _get_logger

logger = _get_logger(__name__)

# ── Date column for each section ──────────────────────────────────────
# Maps section_id -> the most meaningful date column to show as "last data date"
# Uses fetched_at for live snapshot data, date for historical records, etc.
SECTION_DATE_COLUMNS: dict[str, str] = {
    "all-symbols": "fetched_at",
    "symbol-detail": "fetched_at",
    "index-tse": "fetched_at",
    "index-farabours": "fetched_at",
    "index-selected": "fetched_at",
    "nav": "date",
    "option": "fetched_at",
    "transaction": "trade_date",
    "history-price": "date",
    "history-real-legal": "date",
    "candlestick": "date",
    "shareholder": "date",
    "ime-futures": "date_update",
    "ime-options": "fetched_at",
    "ime-certificates": "date_update",
    "ime-funds": "fetched_at",
    "ime-physical": "date_trade",
    "commodity": "fetched_at",
    "crypto": "fetched_at",
    "gold-coin": "fetched_at",
    "gold-coin-history": "date",
    "currency": "fetched_at",
    "currency-history": "fetched_at",
    "codal": "date_publish",
}


# ── Section registry ───────────────────────────────────────────────

SECTIONS: dict[str, dict[str, Any]] = {
    "all-symbols": {
        "name": "تمامی نمادها",
        "name_en": "All Symbols",
        "endpoint": BrsApiEndpoints.ALL_SYMBOLS,
        "model": SymbolSnapshotModel,
        "parser": TsetmcParser.parse_all_symbols,
        "category": "tsetmc",
        "icon": "📊",
        "has_date_range": False,
    },
    "symbol-detail": {
        "name": "جزئیات نمادها",
        "name_en": "Symbol Detail",
        "endpoint": BrsApiEndpoints.SYMBOL_DETAIL,
        "model": SymbolDetailModel,
        "parser": TsetmcParser.parse_symbol_detail,
        "category": "tsetmc",
        "icon": "🔍",
        "has_date_range": False,
    },
    "index-tse": {
        "name": "شاخص بورس",
        "name_en": "TSE Index",
        "endpoint": BrsApiEndpoints.INDEX,
        "model": IndexValueModel,
        "parser": TsetmcParser.parse_index,
        "category": "tsetmc",
        "icon": "📈",
        "has_date_range": False,
        "default_params": {"type": "1"},
    },
    "index-farabours": {
        "name": "شاخص فرابورس",
        "name_en": "IFB Index",
        "endpoint": BrsApiEndpoints.INDEX,
        "model": IndexValueModel,
        "parser": TsetmcParser.parse_index,
        "category": "tsetmc",
        "icon": "📉",
        "has_date_range": False,
        "default_params": {"type": "2"},
    },
    "index-selected": {
        "name": "شاخص‌های منتخب",
        "name_en": "Selected Indices",
        "endpoint": BrsApiEndpoints.INDEX,
        "model": IndexValueModel,
        "parser": TsetmcParser.parse_index,
        "category": "tsetmc",
        "icon": "📊",
        "has_date_range": False,
        "default_params": {"type": "3"},
    },
    "nav": {
        "name": "NAV صندوق (تک‌نماد)",
        "name_en": "Fund NAV (single)",
        "endpoint": BrsApiEndpoints.NAV,
        "model": NavRecordModel,
        "parser": TsetmcParser.parse_nav,
        "category": "tsetmc",
        "icon": "🏦",
        "has_date_range": False,
    },
    "option": {
        "name": "آپشن‌ها",
        "name_en": "Options",
        "endpoint": BrsApiEndpoints.OPTION,
        "model": OptionSnapshotModel,
        "parser": TsetmcParser.parse_options,
        "category": "tsetmc",
        "icon": "🎯",
        "has_date_range": False,
    },
    "transaction": {
        "name": "معاملات",
        "name_en": "Transactions",
        "endpoint": BrsApiEndpoints.TRANSACTION,
        "model": IntradayTradeModel,
        "parser": TsetmcParser.parse_transactions,
        "category": "tsetmc",
        "icon": "💹",
        "has_date_range": True,
        "date_params": ("date",),
    },
    "history-price": {
        "name": "قیمت‌های تاریخی",
        "name_en": "Historical Prices",
        "endpoint": BrsApiEndpoints.HISTORY_PRICE,
        "model": HistoricalDailyModel,
        "parser": TsetmcParser.parse_history_price,
        "category": "tsetmc",
        "icon": "📜",
        "has_date_range": False,
    },
    "history-real-legal": {
        "name": "تغییرات حقیقی/حقوقی",
        "name_en": "Real/Legal History",
        "endpoint": BrsApiEndpoints.HISTORY_REALLEGAL,
        "model": HistoricalRealLegalModel,
        "parser": TsetmcParser.parse_history_real_legal,
        "category": "tsetmc",
        "icon": "👥",
        "has_date_range": False,
    },
    "candlestick": {
        "name": "کندل‌استیک",
        "name_en": "Candlesticks",
        "endpoint": BrsApiEndpoints.CANDLESTICK,
        "model": CandlestickModel,
        "parser": TsetmcParser.parse_candlesticks,
        "category": "tsetmc",
        "icon": "🕯️",
        "has_date_range": False,
    },
    "shareholder": {
        "name": "سهامداران",
        "name_en": "Shareholders",
        "endpoint": BrsApiEndpoints.SHAREHOLDER,
        "model": ShareholderRecordModel,
        "parser": TsetmcParser.parse_shareholders,
        "category": "tsetmc",
        "icon": "🏛️",
        "has_date_range": True,
        "date_params": ("date",),
    },
    "ime-futures": {
        "name": "آتی بورس کالا",
        "name_en": "IME Futures",
        "endpoint": BrsApiEndpoints.IME_FUTURES,
        "model": ImeFutureModel,
        "parser": ImeParser.parse_futures,
        "category": "ime",
        "icon": "🛢️",
        "has_date_range": False,
    },
    "ime-options": {
        "name": "اختیار بورس کالا",
        "name_en": "IME Options",
        "endpoint": BrsApiEndpoints.IME_OPTION,
        "model": ImeOptionModel,
        "parser": ImeParser.parse_options,
        "category": "ime",
        "icon": "📋",
        "has_date_range": False,
    },
    "ime-certificates": {
        "name": "گواهی سپرده کالایی",
        "name_en": "IME Certificates",
        "endpoint": BrsApiEndpoints.IME_CERTIFICATE,
        "model": ImeCertificateModel,
        "parser": ImeParser.parse_certificates,
        "category": "ime",
        "icon": "📜",
        "has_date_range": False,
    },
    "ime-funds": {
        "name": "صندوق‌های کالایی",
        "name_en": "IME Funds",
        "endpoint": BrsApiEndpoints.IME_FUND,
        "model": ImeFundModel,
        "parser": ImeParser.parse_funds,
        "category": "ime",
        "icon": "💰",
        "has_date_range": False,
    },
    "ime-physical": {
        "name": "معاملات فیزیکی",
        "name_en": "IME Physical",
        "endpoint": BrsApiEndpoints.IME_PHYSICAL,
        "model": ImePhysicalTradeModel,
        "parser": ImeParser.parse_physical_trades,
        "category": "ime",
        "icon": "⚖️",
        "has_date_range": True,
        "date_params": ("date_start", "date_end"),
    },
    "commodity": {
        "name": "کامودیتی‌ها",
        "name_en": "Commodities",
        "endpoint": BrsApiEndpoints.COMMODITY,
        "model": CommodityPriceModel,
        "parser": CommodityParser.parse,
        "category": "commodity",
        "icon": "🌍",
        "has_date_range": False,
    },
    "crypto": {
        "name": "ارزهای دیجیتال",
        "name_en": "Cryptocurrencies",
        "endpoint": BrsApiEndpoints.CRYPTOCURRENCY,
        "model": CryptoPriceModel,
        "parser": CryptoParser.parse,
        "category": "cryptocurrency",
        "icon": "₿",
        "has_date_range": False,
    },
    "gold-coin": {
        "name": "طلا و سکه",
        "name_en": "Gold & Coins",
        "endpoint": BrsApiEndpoints.GOLD_COIN,
        "model": GoldCoinPriceModel,
        "parser": GoldCoinParser.parse,
        "category": "commodity",
        "icon": "🥇",
        "has_date_range": False,
    },
    "gold-coin-history": {
        "name": "تاریخچه طلا",
        "name_en": "Gold History",
        "endpoint": BrsApiEndpoints.GOLD_COIN_HISTORY,
        "model": GoldCoinHistoryModel,
        "parser": GoldCoinParser.parse_history,
        "category": "commodity",
        "icon": "📅",
        "has_date_range": True,
        "date_params": ("date_start", "date_end"),
    },
    "currency": {
        "name": "نرخ ارز",
        "name_en": "Currency",
        "endpoint": BrsApiEndpoints.CURRENCY,
        "model": CurrencyPriceModel,
        "parser": CurrencyParser.parse,
        "category": "commodity",
        "icon": "💵",
        "has_date_range": False,
    },
    "currency-history": {
        "name": "تاریخچه ارز",
        "name_en": "Currency History",
        "endpoint": BrsApiEndpoints.CURRENCY_HISTORY,
        "model": CurrencyPriceModel,
        "parser": CurrencyParser.parse_history,
        "category": "commodity",
        "icon": "📊",
        "has_date_range": True,
        "date_params": ("date_start", "date_end"),
    },
    # gold-24h and currency-24h removed — API endpoints now return 404.
    # Data is available via the combined Gold_Currency.php endpoint.
    "codal": {
        "name": "اطلاعیه‌های کدال",
        "name_en": "Codal Announcements",
        "endpoint": BrsApiEndpoints.CODAL_ANNOUNCEMENT,
        "model": CodalAnnouncementModel,
        "parser": CodalParser.parse_announcements_only,
        "category": "codal",
        "icon": "🏢",
        "has_date_range": True,
        "date_params": ("date_start", "date_end"),
    },
}


@router.get("/manage/sections", summary="List all BrsApi sections with status")
async def list_sections(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return all BrsApi sections with sync status, record count, and last update.

    Uses parallel queries (asyncio.gather) for fast loading even with large tables.
    Row counts use PostgreSQL statistics (pg_stat_user_tables) when available,
    falling back to COUNT(*) for individual tables.
    """
    import asyncio

    sync_repo = SyncLogRepository(session)

    # Get row estimates from pg_stat for fast approximate counts
    pg_stat_counts: dict[str, int] = {}
    try:
        pg_result = await session.execute(text(
            "SELECT relname, n_live_tup FROM pg_stat_user_tables "
            "WHERE schemaname = 'public'"
        ))
        for row in pg_result:
            pg_stat_counts[row[0]] = row[1] or 0
    except Exception:
        pass

    async def build_section(section_id: str, cfg: dict[str, Any]) -> dict[str, Any]:
        try:
            model = cfg["model"]
            endpoint_path = cfg["endpoint"].path
            table_name = model.__tablename__

            # Use pg_stat estimate for fast row count, fall back to COUNT(*)
            count = pg_stat_counts.get(table_name)
            if count is None:
                try:
                    stmt = select(sa_func.count()).select_from(model)
                    cnt_result = await session.execute(stmt)
                    count = cnt_result.scalar() or 0
                except Exception:
                    count = 0

            # Query last data date in parallel with sync log
            date_col = SECTION_DATE_COLUMNS.get(section_id)

            async def get_last_data_date():
                if not date_col or not count:
                    return None
                try:
                    col = getattr(model, date_col, None)
                    if col is None:
                        return None
                    date_stmt = select(sa_func.max(col)).select_from(model)
                    date_result = await session.execute(date_stmt)
                    val = date_result.scalar()
                    return str(val) if val else None
                except Exception:
                    return None

            async def get_last_sync():
                try:
                    return await sync_repo.last_sync(endpoint_path, max_age_seconds=999999999)
                except Exception:
                    return None

            # Run date query and sync log query in parallel
            last_data_date, last = await asyncio.gather(
                get_last_data_date(),
                get_last_sync(),
            )

            return {
                "id": section_id,
                "name": cfg["name"],
                "name_en": cfg["name_en"],
                "icon": cfg["icon"],
                "category": cfg["category"],
                "has_date_range": cfg["has_date_range"],
                "record_count": count,
                "last_data_date": last_data_date,
                "last_sync": {
                    "status": last.status if last else None,
                    "items_count": last.items_count if last else 0,
                    "duration_ms": last.duration_ms if last else 0.0,
                    "completed_at": str(last.completed_at) if last and last.completed_at else None,
                    "error_message": last.error_message if last else None,
                } if last else None,
            }
        except Exception:
            return {
                "id": section_id,
                "name": cfg.get("name", section_id),
                "name_en": cfg.get("name_en", ""),
                "icon": cfg.get("icon", "📦"),
                "category": cfg.get("category", "other"),
                "has_date_range": cfg.get("has_date_range", False),
                "record_count": 0,
                "last_data_date": None,
                "last_sync": None,
            }

    # Run ALL section queries in parallel
    results = await asyncio.gather(*[
        build_section(sid, cfg) for sid, cfg in SECTIONS.items()
    ])

    return ApiResponse[list[dict[str, Any]]](success=True, data=list(results))


@router.post("/manage/sync/{section_id}", summary="Sync a BrsApi section")
async def sync_section(
    section_id: str,
    date_start: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_end: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    symbol: str | None = Query(None, description="Symbol for symbol-specific endpoints"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Fetch data from BrsApi for a given section and store in PostgreSQL."""
    cfg = SECTIONS.get(section_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")

    client = await get_client()
    from brsapi.services.sync_service import BrsApiSyncService
    sync_svc = BrsApiSyncService(client=client, session=session)

    params: dict[str, str] = dict(cfg.get("default_params") or {})
    if date_start and cfg["has_date_range"]:
        params["date_start"] = date_start
    if date_end and cfg["has_date_range"]:
        params["date_end"] = date_end
    if symbol:
        params["l18"] = symbol

    parser_fn = cfg["parser"]
    if symbol and section_id in ("history-price", "history-real-legal"):
        _sym = symbol
        _orig_parser = parser_fn
        def _parser_with_sym(data: Any) -> list[dict[str, Any]]:
            records = _orig_parser(data)
            for r in records:
                r["symbol"] = _sym
            return records
        parser_fn = _parser_with_sym

    try:
        report = await sync_svc.sync(
            endpoint=cfg["endpoint"],
            parser=parser_fn,
            model_class=cfg["model"],
            params=params or None,
            category_override=cfg["category"],
            session=session,
        )

        return ApiResponse[dict[str, Any]](success=report.success, data={
            "endpoint": report.endpoint,
            "section_id": section_id,
            "success": report.success,
            "items_count": report.items_count,
            "duration_ms": report.duration_ms,
            "skipped": report.skipped,
            "error": report.error,
        })
    except Exception as exc:
        from core.logging import get_logger
        logger = get_logger(__name__)
        logger.exception("Sync failed for section %s", section_id)
        return ApiResponse[dict[str, Any]](
            success=False,
            data={"section_id": section_id, "error": str(exc)},
        )


@router.get("/manage/download/{section_id}", summary="Download BrsApi section data")
async def download_section(
    section_id: str,
    format: str = Query("json", description="Download format: json or csv"),
    live: bool = Query(False, description="Fetch fresh data from API instead of reading from DB"),
    date_start: str | None = Query(None, description="Start date (YYYY-MM-DD) for date-range sections"),
    date_end: str | None = Query(None, description="End date (YYYY-MM-DD) for date-range sections"),
    symbol: str | None = Query(None, description="Symbol for symbol-specific endpoints"),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Download data from a BrsApi section as JSON or CSV.

    By default reads from the database. Use ``?live=true`` to fetch
    fresh data from the BrsApi directly (bypasses the DB).
    """
    cfg = SECTIONS.get(section_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")

    if live:
        client = await get_client()

        params: dict[str, str] = dict(cfg.get("default_params") or {})
        if date_start and cfg.get("has_date_range"):
            params["date_start"] = date_start
        if date_end and cfg.get("has_date_range"):
            params["date_end"] = date_end
        if symbol:
            params["l18"] = symbol

        result = await client.fetch(cfg["endpoint"], params=params or None, category_override=cfg.get("category"))
        if not result.success:
            raise HTTPException(status_code=502, detail=f"API fetch failed: {result.error}")

        try:
            records = cfg["parser"](result.value.data)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Parse error: {exc}")

        if isinstance(records, dict):
            records_list = [records] if records else []
        elif isinstance(records, list):
            records_list = records
        else:
            records_list = []

        data = records_list
        filename = f"brsapi_{section_id}_live"

        if format == "csv":
            if not data:
                return Response(content="", media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}.csv"})
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            return Response(
                content=output.getvalue(),
                media_type="text/csv; charset=utf-8-sig",
                headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
            )

        return Response(
            content=json.dumps(data, ensure_ascii=False, default=str),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}.json"},
        )

    model = cfg["model"]
    stmt = select(model).order_by(model.created_at.desc()) if hasattr(model, "created_at") else select(model)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    data = []
    for row in rows:
        d = {c.key: getattr(row, c.key) for c in row.__table__.columns if c.key not in ("raw_json",)}
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        data.append(d)

    filename = f"brsapi_{section_id}"

    if format == "csv":
        if not data:
            return Response(content="", media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}.csv"})
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        content = output.getvalue()
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
        )

    return Response(
        content=json.dumps(data, ensure_ascii=False, default=str),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}.json"},
    )


# ── ETF symbols list (common Iranian ETF funds supported by BrsAPI) ──
BRSAPI_ETF_SYMBOLS: list[str] = [
    "اهرم", "توان", "شتاب", "جهش", "موج", "نارنج اهرم", "بيدار", "دوايكس",
    "پيشران", "اطلس", "آساس", "كاريس", "الماس", "فيروزه", "كاردان", "ثروتم",
    "آگاس", "آتيمس", "افق ملت", "سرو", "بذر", "دارا يكم", "ارزش", "آوا",
    "مدير", "پالايش", "زرين", "وبازار", "فراز", "ثهام", "پادا", "داريوش",
    "ويستا", "اوج", "ثمين", "انار", "رماس", "پتروما", "تاراز", "مرواريد",
    "آرام", "سلام", "هم وزن", "درسا", "برليان", "عقيق", "هيوا", "ثنا",
    "ترمه", "دريا", "پرتو", "اكسيژن", "پتروآگاه", "استيل", "پتروداريوش",
    "صدف", "پتروصبا", "سمان", "هوشيار", "بهين رو", "تيام", "پيروز", "رويين",
    "فلزفارابي", "متال", "آذرين", "خليج", "جاودان", "هامون", "نارين",
    "پتروآبان", "فارما كيان", "تكپاد", "بازبيمه", "تخت گاز", "ثروت ساز",
    "سپينود", "خبرگان", "آبنوس", "رخش", "پتروفارس", "فرصت", "رسانا", "مانا",
    "پتروپاداش", "هومان", "سيمانيا", "رشدي كيان", "دي سهام", "جوانه كوچك",
    "عرش", "همتا", "فارماني", "آس", "ابتكار", "آميتيس", "پناه", "رونق",
    "فرا الگوريتم", "سهامدار", "هوشمند", "ديار", "پرتوسا", "رويش همراه",
    "بانكدار", "اعتبارسهام", "يلدا", "لذيذ", "هم تراز", "آلكان", "يكم",
    "سها", "كوانتوم", "بزرگ", "همسنگ", "هم ارز", "نبات", "جام سهند",
    "رادان", "پتروسورين", "ثروين", "امتياز", "ولتاژ", "بانكو", "ناوگان",
    "بانكيا", "آويد", "آوان", "آسام", "صنوين", "زيتون", "آفرين", "هيبريد",
    "شيلد", "مختلط", "تداوم", "اعتماد", "صايند", "سخند", "آكورد", "پارند",
    "كيان", "امين يكم", "كمند", "فيروزا", "اوصتا", "آساميد", "دارا",
    "ارمغان", "گنجينه", "تصميم", "افران", "گنجين", "ياقوت", "داريك", "سپر",
    "خاتم", "فردا", "كارين", "سپيدما", "كامياب", "سيناد", "هماي", "ماني",
    "ثبات", "كارا", "يارا", "هامرز", "رشد", "پاداش", "نشان", "آفاق", "آوند",
    "نخل", "ساحل", "لبخند", "كاج", "رايكا", "بازده", "اعتبار", "پايا",
    "ديبا", "رابين", "سام", "درين", "نيلي", "صنهال", "آكام", "آلا", "فاخر",
    "طلوع", "توسكا", "خورشيد", "اونيكس", "ثابت اكسيژن", "دامون", "ماهور",
    "بمان", "پايش", "اصيل", "كارما", "همگام", "نيك گستر", "آتيه ملت",
    "آرامش", "شميم", "ترنج ثابت", "اطمينان", "اركيده", "خزانه ملت",
    "كارآمد", "آسود", "زمرد كوروش", "ستاره", "سپنتارود", "پاسارگاد",
    "بلوط", "آسان", "اندوخته داريوش", "ماكان", "هدف", "آسا", "ثمر",
    "رايبد", "سيلور", "سيمين", "رويش", "آتي1", "آشناتك", "تهران1",
    "فنابا", "پارتين", "ونچر", "نوآور", "استارز", "ثروت", "كمان",
    "پيشرفت", "ديوان", "سپهر", "اكسير", "ديتا", "تهران2", "افق نگر",
    "تدبيريكم", "بامداد", "صنم", "تمشك", "خوشه", "ضمان", "گارانتي",
    "طلا", "زر", "گوهر", "عيار", "كهربا", "مثقال", "زرفام", "نفيس",
    "گنج", "ناب", "آلتون", "جواهر", "تابش", "ليان", "زروان", "درخشان",
    "آتش", "قيراط", "گلديس", "زمرد", "امرالد", "رز ترنج", "درنا", "زرگر",
    "ريتون", "گلدا", "رزگلد", "نگين فارس", "هميان", "ميراث", "دفينه",
]


@router.post("/manage/sync-nav-all", summary="Batch sync NAV for all ETF funds")
async def sync_nav_all(
    max_symbols: int = Query(0, ge=0, le=500, description="Max symbols to sync (0 = all ETFs)"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """
    Batch-sync NAV (Net Asset Value) for all ETF fund symbols.

    Iterates through the known ETF symbol list, fetches NAV data from
    BrsApi for each, and stores the results. Uses rate limiting to
    stay within BrsApi's per-minute limits (6 req/min for NAV endpoint).
    """
    import asyncio as _asyncio

    client = await get_client()
    from brsapi.services.sync_service import BrsApiSyncService

    sync_svc = BrsApiSyncService(client=client, session=session)

    symbols = BRSAPI_ETF_SYMBOLS[:max_symbols] if max_symbols > 0 else BRSAPI_ETF_SYMBOLS

    results: list[dict[str, Any]] = []
    success_count = 0
    fail_count = 0
    total_duration_ms = 0.0

    for i, symbol in enumerate(symbols):
        # Rate limit: NAV = 6 req/min → wait 11s between requests
        await _asyncio.sleep(11)
        try:
            report = await sync_svc.sync_nav(session, symbol)
            total_duration_ms += report.duration_ms
            if report.success:
                success_count += 1
            else:
                fail_count += 1
            results.append({
                "symbol": symbol,
                "success": report.success,
                "items_count": report.items_count,
                "duration_ms": report.duration_ms,
                "error": report.error,
            })
            if (i + 1) % 10 == 0:
                logger.info("NAV sync progress: %d/%d symbols (%d ok, %d fail)",
                           i + 1, len(symbols), success_count, fail_count)
        except Exception as exc:
            fail_count += 1
            results.append({
                "symbol": symbol,
                "success": False,
                "error": str(exc),
            })

    return ApiResponse[dict[str, Any]](success=True, data={
        "total": len(symbols),
        "success_count": success_count,
        "fail_count": fail_count,
        "total_duration_ms": round(total_duration_ms, 1),
        "results": results,
    })


@router.post("/manage/sync-top-symbols", summary="Sync Symbol.php for top N symbols")
async def sync_top_symbols(
    limit: int = Query(10, ge=1, le=50, description="Number of top symbols to sync"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """
    Batch-sync enriched symbol details (Symbol.php) for the top N symbols
    sorted by trade value (most active).

    Returns a summary report with per-symbol results.
    """

    client = await get_client()
    from brsapi.services.sync_service import BrsApiSyncService

    sync_svc = BrsApiSyncService(client=client, session=session)

    # 1. Get top symbols by trade value from snapshots
    try:
        stmt = (
            select(SymbolSnapshotModel.symbol)
            .order_by(SymbolSnapshotModel.trade_value.desc().nullslast())
            .limit(limit)
        )
        result = await session.execute(stmt)
        symbols = [row[0] for row in result if row[0]]
    except Exception as exc:
        return ApiResponse[dict[str, Any]](success=False, data={"error": f"Failed to query symbols: {exc}"})

    if not symbols:
        return ApiResponse[dict[str, Any]](success=False, data={"error": "No symbols found in database"})

    # 2. Sync details for each symbol sequentially
    results: list[dict[str, Any]] = []
    success_count = 0
    fail_count = 0
    total_duration_ms = 0.0

    for symbol in symbols:
        # Small delay between requests to avoid rate limiting (~30 req/min for TSETMC)
        await asyncio.sleep(2)
        try:
            report = await sync_svc.sync_symbol_detail(session, symbol)
            total_duration_ms += report.duration_ms
            if report.success:
                success_count += 1
            else:
                fail_count += 1
            results.append({
                "symbol": symbol,
                "success": report.success,
                "items_count": report.items_count,
                "duration_ms": report.duration_ms,
                "error": report.error,
            })
        except Exception as exc:
            fail_count += 1
            results.append({
                "symbol": symbol,
                "success": False,
                "error": str(exc),
            })

    return ApiResponse[dict[str, Any]](success=True, data={
        "total": len(symbols),
        "success_count": success_count,
        "fail_count": fail_count,
        "total_duration_ms": round(total_duration_ms, 1),
        "results": results,
    })


@router.post("/manage/sync-all-history", summary="Sync history for ALL symbols")
async def sync_all_history(
    limit: int = Query(0, ge=0, le=2000, description="Max symbols (0 = all)"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """
    Fetch historical daily prices for ALL symbols in the database,
    ordered by symbol name. For each symbol, fetches all available
    history from the earliest date.
    """
    import asyncio

    client = await get_client()
    from brsapi.services.sync_service import BrsApiSyncService

    sync_svc = BrsApiSyncService(client=client, session=session)

    # Get all symbols from brsapi_symbol_snapshots, ordered by name
    try:
        stmt = select(SymbolSnapshotModel.symbol).order_by(SymbolSnapshotModel.symbol)
        if limit > 0:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        symbols = [row[0] for row in result if row[0]]
    except Exception as exc:
        return ApiResponse[dict[str, Any]](success=False, data={"error": f"Failed to query symbols: {exc}"})

    if not symbols:
        return ApiResponse[dict[str, Any]](success=False, data={"error": "No symbols found"})

    results: list[dict[str, Any]] = []
    success_count = 0
    fail_count = 0
    total_duration_ms = 0.0

    for i, symbol in enumerate(symbols):
        # Delay between requests (TSETMC rate limit ~30 req/min)
        await asyncio.sleep(2)
        try:
            report = await sync_svc.sync_history_price(session, symbol)
            total_duration_ms += report.duration_ms
            if report.success:
                success_count += 1
            else:
                fail_count += 1
            results.append({
                "symbol": symbol,
                "success": report.success,
                "items_count": report.items_count,
                "duration_ms": report.duration_ms,
                "error": report.error,
            })
            # Log progress every 10 symbols
            if (i + 1) % 10 == 0:
                logger.info("History sync progress: %d/%d symbols", i + 1, len(symbols))
        except Exception as exc:
            fail_count += 1
            results.append({
                "symbol": symbol,
                "success": False,
                "error": str(exc),
            })

    return ApiResponse[dict[str, Any]](success=True, data={
        "total": len(symbols),
        "success_count": success_count,
        "fail_count": fail_count,
        "total_duration_ms": round(total_duration_ms, 1),
        "results": results,
    })


@router.get("/manage/last-update/{section_id}", summary="Last update time for a section")
async def section_last_update(
    section_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any] | None]:
    """Return the most recent sync log for a given section."""
    cfg = SECTIONS.get(section_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")

    sync_repo = SyncLogRepository(session)
    last = await sync_repo.last_sync(cfg["endpoint"].path, max_age_seconds=999999999)

    if not last:
        return ApiResponse[dict[str, Any] | None](success=True, data=None)

    return ApiResponse[dict[str, Any] | None](success=True, data={
        "status": last.status,
        "items_count": last.items_count,
        "duration_ms": last.duration_ms,
        "completed_at": str(last.completed_at) if last.completed_at else None,
        "error_message": last.error_message,
    })
