"""
BrsApi endpoints — commodity & cryptocurrency realtime data.

Provides read-only access to cached commodity and cryptocurrency prices
fetched from BrsApi.ir and stored in PostgreSQL.
"""

from __future__ import annotations

import asyncio
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
from brsapi.constants import BRSAPI_ETF_SYMBOLS
from brsapi.services.query_service import BrsApiQueryService
from core.db_utils import safe_row_str
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
        logger.exception("BrsApi health check failed")
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
        logger.exception("Failed to fetch commodity prices")
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
        logger.exception("Failed to fetch commodity categories")
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
        logger.exception("Failed to fetch crypto prices")
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
        logger.exception("Failed to fetch top crypto")
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
        logger.exception("Failed to fetch gold/coin prices")
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
        logger.exception("Failed to fetch currency prices")
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
        logger.debug("HistoricalDailyModel query failed for %s — falling through to quotes table", symbol)

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
                data=PaginatedResult[dict[str, Any]](items=[], total=0, page=1, page_size=limit, total_pages=1),
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
        logger.exception("Failed to fetch historical daily for %s", symbol)
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
                logger.debug("instrument_names lookup failed for %d instrument_ids", len(instr_ids))

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
        logger.exception("Failed to fetch codal announcements")
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult[dict[str, Any]](items=[], total=0, page=1, page_size=page_size, total_pages=1),
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
        logger.exception("Failed to fetch lazy codal announcements for %s", symbol)
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
    GoldCurrencyParser,
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
        # /Market/Coin.php is dead (HTTP 404 since ~June 2026) — fetch the
        # combined /Market/Gold_Currency.php payload and extract the gold
        # section instead (see GoldCurrencyParser.parse_gold).
        "endpoint": BrsApiEndpoints.GOLD_CURRENCY,
        "model": GoldCoinPriceModel,
        "parser": GoldCurrencyParser.parse_gold,
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
        # /Market/Currency.php is dead (HTTP 404 since ~June 2026) — fetch the
        # combined /Market/Gold_Currency.php payload and extract the currency
        # section instead (see GoldCurrencyParser.parse_currency).
        "endpoint": BrsApiEndpoints.GOLD_CURRENCY,
        "model": CurrencyPriceModel,
        "parser": GoldCurrencyParser.parse_currency,
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
        except Exception as exc:
            logger.warning("build_section failed for %s: %s", section_id, exc)
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
    candle_type: str = Query("3", alias="type", description="Candlestick type: 1=realtime, 2=unadjusted, 3=adjusted"),
    count: int | None = Query(None, ge=1, le=2000, description="Number of candles to request (candlestick only)"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Fetch data from BrsApi for a given section and store in PostgreSQL."""
    cfg = SECTIONS.get(section_id)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")

    client = await get_client()
    from brsapi.services.sync_service import BrsApiSyncService
    sync_svc = BrsApiSyncService(client=client, session=session)

    # Candlestick has a dedicated convenience method that attaches
    # symbol + candle_type to every record (the generic path would leave
    # both empty) — use it whenever a symbol is given.
    if section_id == "candlestick" and symbol:
        try:
            report = await sync_svc.sync_candlesticks(
                session, symbol, candle_type=candle_type, count=count
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
            logger.exception("Sync failed for section %s", section_id)
            return ApiResponse[dict[str, Any]](
                success=False,
                data={"section_id": section_id, "error": str(exc)},
            )

    params: dict[str, str] = dict(cfg.get("default_params") or {})
    if date_start and cfg["has_date_range"]:
        params["date_start"] = date_start
    if date_end and cfg["has_date_range"]:
        params["date_end"] = date_end
    if symbol:
        params["l18"] = symbol

    parser_fn = cfg["parser"]
    if symbol and section_id in ("history-price", "history-real-legal", "candlestick"):
        _sym = symbol
        _orig_parser = parser_fn
        def _parser_with_sym(data: Any) -> list[dict[str, Any]]:
            records = _orig_parser(data)
            for r in records:
                r["symbol"] = _sym
                if section_id == "candlestick":
                    r["candle_type"] = candle_type
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


# ── Symbol Details (brsapi_symbol_details) ────────────────────────
# Read-only access to the enriched per-symbol data (Symbol.php endpoint).
# One row per symbol — the latest fetched version is kept (upserted on sync).


def _symbol_detail_dict(row: Any) -> dict[str, Any]:
    """Convert a SymbolDetailModel row to a plain dict (skip heavy raw_json)."""
    d: dict[str, Any] = {}
    for c in row.__table__.columns:
        if c.key in ("raw_json",):
            continue
        val = getattr(row, c.key)
        if isinstance(val, datetime):
            val = val.isoformat()
        d[c.key] = val
    return d


@router.get(
    "/symbol-details",
    summary="List symbol details (brsapi_symbol_details)",
    description="Paginated list of enriched symbol details read from the database. "
    "Supports search by symbol/name, market filter, and sorting.",
)
async def list_symbol_details(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    q: str | None = Query(None, description="Search by symbol or company name"),
    market: str | None = Query(None, description="Filter by market (e.g. بورس / فرابورس)"),
    sort_by: str = Query("updated_at", description="Sort field: updated_at | symbol | price_last | market_value | trade_value"),
    order: str = Query("desc", description="Sort order: asc | desc"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[PaginatedResult[dict[str, Any]]]:
    """Return enriched symbol details from the ``brsapi_symbol_details`` table."""
    try:
        conditions = []
        if q:
            like = f"%{q.strip()}%"
            from sqlalchemy import or_

            conditions.append(
                or_(
                    SymbolDetailModel.symbol.ilike(like),
                    SymbolDetailModel.name.ilike(like),
                    SymbolDetailModel.name_en.ilike(like),
                )
            )
        if market:
            conditions.append(SymbolDetailModel.market == market)

        count_stmt = select(sa_func.count()).select_from(SymbolDetailModel).where(*conditions)
        total = (await session.execute(count_stmt)).scalar() or 0

        sort_map = {
            "updated_at": SymbolDetailModel.updated_at,
            "symbol": SymbolDetailModel.symbol,
            "price_last": SymbolDetailModel.price_last,
            "market_value": SymbolDetailModel.market_value,
            "trade_value": SymbolDetailModel.trade_value,
            "pe_ratio": SymbolDetailModel.pe_ratio,
        }
        order_col = sort_map.get(sort_by, SymbolDetailModel.updated_at)
        order_expr = order_col.desc() if order.lower() == "desc" else order_col.asc()
        # Nulls last so rows with missing sort values don't hide populated ones.
        order_expr = order_expr.nullslast()

        offset = (page - 1) * page_size
        stmt = (
            select(SymbolDetailModel)
            .where(*conditions)
            .order_by(order_expr, SymbolDetailModel.symbol.asc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await session.execute(stmt)).scalars().all()
        items = [_symbol_detail_dict(r) for r in rows]

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
        logger.exception("Failed to list symbol details")
        return ApiResponse[PaginatedResult[dict[str, Any]]](
            success=False,
            data=PaginatedResult[dict[str, Any]](items=[], total=0, page=1, page_size=page_size, total_pages=1),
            error={"message": str(exc)},
        )


@router.get(
    "/symbol-details/{symbol}",
    summary="Get symbol detail",
    description="Full enriched detail for a single symbol from brsapi_symbol_details (by symbol or ins_id)",
)
async def get_symbol_detail(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Return the complete enriched detail row for one symbol."""
    try:
        from sqlalchemy import or_

        stmt = (
            select(SymbolDetailModel)
            .where(
                or_(
                    SymbolDetailModel.symbol == symbol,
                    SymbolDetailModel.ins_id == symbol,
                )
            )
            .order_by(SymbolDetailModel.updated_at.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalars().first()
        if row is None:
            return ApiResponse[dict[str, Any]](success=False, error={"message": f"Symbol detail not found: {symbol}"})
        return ApiResponse[dict[str, Any]](success=True, data=_symbol_detail_dict(row))
    except Exception as exc:
        logger.exception("Failed to fetch symbol detail for %s", symbol)
        return ApiResponse[dict[str, Any]](success=False, error={"message": str(exc)})


# ETF symbol list moved to brsapi/constants.py so it can be reused
# by the sync service without depending on the API layer.
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

    NOTE: this is the legacy BLOCKING variant — prefer the background
    ``/manage/sync-all-history-price`` backfill for full-market runs so
    the HTTP request does not stay open for hours.
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


# ── Manual full-market candlestick backfill (admin-triggered) ────────
# The whole market (~1,900 symbols × 3 candle types × 11s spacing) takes
# several hours, so the run happens as a background task whose live state
# is kept in memory and polled by the manage UI. Single-process uvicorn
# (default) is assumed — enough for the admin panel.

_CANDLE_BACKFILL_STATE: dict[str, Any] = {
    "status": "idle",          # idle | running | done | cancelled | error
    "started_at": None,
    "finished_at": None,
    "total_symbols": 0,
    "processed": 0,
    "ok": 0,
    "fail": 0,
    "items": 0,
    "current_symbol": None,
    "message": None,
    "error": None,
    "cancel_requested": False,
}
_candle_backfill_task: asyncio.Task | None = None


def _mask_api_key(key: str) -> str:
    """Show only the first/last few characters of an API key."""
    if not key:
        return ""
    if len(key) <= 8:
        return (key[0] + "***" + key[-1]) if len(key) > 3 else "***"
    return f"{key[:4]}…{key[-4:]}"


def _count_payload(data: Any) -> int:
    """Best-effort item count of a BrsApi payload (list or dict)."""
    if data is None:
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("symbols", "data", "items", "result", "results"):
            if isinstance(data.get(key), list):
                return len(data[key])
        return len(data)
    return 0


async def _run_candle_backfill(max_symbols: int, allow_weekend: bool) -> None:
    """Background worker for the manual full-market candlestick backfill.

    Reuses the job registry's ``_run_candlesticks_all`` so the daily job
    and the manual trigger share identical logic; live progress is written
    into ``_CANDLE_BACKFILL_STATE``.
    """
    from core.database import get_session

    from brsapi.jobs.registry import get_brsapi_job_registry
    from brsapi.services.sync_service import BrsApiSyncService

    state = _CANDLE_BACKFILL_STATE
    try:
        client = await get_client()
        registry = get_brsapi_job_registry()
        async for session in get_session():
            service = BrsApiSyncService(client=client, session=session)
            report = await registry._run_candlesticks_all(
                session,
                service,
                max_symbols=max_symbols,
                allow_weekend=allow_weekend,
                progress=state,
            )
            if report is None:
                state["status"] = "error"
                state["error"] = "هیچ نمادی برای بکفیل پیدا نشد"
            elif state["status"] == "running" and report.skipped and report.items_count == 0:
                # Weekend guard hit (allow_weekend=false) — clean skip,
                # not an error. (Cancelled runs already set status themselves.)
                state["status"] = "done"
                state["message"] = "بکفیل اجرا نشد — روز آخر هفته تهران"
            break
    except Exception as exc:
        logger.exception("Manual candlestick backfill failed")
        state["status"] = "error"
        state["error"] = str(exc)
    finally:
        state["finished_at"] = datetime.now().isoformat()
        if state["status"] == "running":
            state["status"] = "error"
            state["error"] = state.get("error") or "بکفیل به‌طور غیرمنتظره متوقف شد"


@router.post(
    "/manage/sync-all-candlesticks",
    summary="Download candlesticks for ALL symbols (manual)",
    description="Trigger a full-market candlestick backfill in the background: AllSymbols + adjusted/unadjusted/realtime candles for every symbol",
)
async def sync_all_candlesticks(
    max_symbols: int = Query(0, ge=0, le=2000, description="Max symbols (0 = all symbols)"),
    allow_weekend: bool = Query(True, description="Allow the run even on Tehran weekends (manual override)"),
) -> ApiResponse[dict[str, Any]]:
    """
    Start a background download of all three candlestick types for the
    whole market.

    The run is rate-limited to 2 req/10s by the API, so a full market
    (~1,900 symbols) takes several hours. Poll
    ``/manage/sync-all-candlesticks/status`` for live progress, or use
    ``/manage/sync-all-candlesticks/cancel`` to stop it.
    """
    global _candle_backfill_task

    if _CANDLE_BACKFILL_STATE["status"] == "running":
        return ApiResponse[dict[str, Any]](success=False, data={
            "started": False,
            "status": "running",
            "message": "یک بکفیل در حال اجراست — پس از اتمام آن دوباره تلاش کنید",
        })

    _CANDLE_BACKFILL_STATE.update({
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "total_symbols": 0,
        "processed": 0,
        "ok": 0,
        "fail": 0,
        "items": 0,
        "current_symbol": None,
        "cancel_requested": False,
        "message": "در حال راه‌اندازی...",
        "error": None,
    })
    _candle_backfill_task = asyncio.create_task(_run_candle_backfill(max_symbols, allow_weekend))
    return ApiResponse[dict[str, Any]](success=True, data={
        "started": True,
        "status": "running",
        "max_symbols": max_symbols if max_symbols > 0 else "all",
        "message": "بکفیل کندل همه نمادها شروع شد — پیشرفت را از همین صفحه پیگیری کنید",
    })


@router.get("/manage/sync-all-candlesticks/status", summary="Status of the manual candlestick backfill")
async def sync_all_candlesticks_status() -> ApiResponse[dict[str, Any]]:
    """Return live progress of the manual full-market candlestick backfill."""
    return ApiResponse[dict[str, Any]](success=True, data=dict(_CANDLE_BACKFILL_STATE))


@router.post("/manage/sync-all-candlesticks/cancel", summary="Cancel the manual candlestick backfill")
async def cancel_sync_all_candlesticks() -> ApiResponse[dict[str, Any]]:
    """Request cancellation of the running backfill (stops after the current symbol)."""
    if _CANDLE_BACKFILL_STATE["status"] != "running":
        return ApiResponse[dict[str, Any]](success=False, data={
            "cancelled": False,
            "message": "هیچ بکفیلی در حال اجرا نیست",
        })
    _CANDLE_BACKFILL_STATE["cancel_requested"] = True
    return ApiResponse[dict[str, Any]](success=True, data={
        "cancelled": True,
        "message": "لغو درخواست شد — پس از نماد جاری متوقف می‌شود",
    })


# ── Manual full-market shareholder backfill (admin-triggered) ────────
# Same background-task pattern as the candlestick backfill above.
# ~1,900 symbols × 5s spacing takes ~2.5 hours, so the run happens as a
# background task whose live state is polled by the manage UI.

_SHAREHOLDER_BACKFILL_STATE: dict[str, Any] = {
    "status": "idle",          # idle | running | done | cancelled | error
    "started_at": None,
    "finished_at": None,
    "total_symbols": 0,
    "processed": 0,
    "ok": 0,
    "fail": 0,
    "items": 0,
    "current_symbol": None,
    "message": None,
    "error": None,
    "cancel_requested": False,
}
_shareholder_backfill_task: asyncio.Task | None = None


async def _run_shareholder_backfill(max_symbols: int, allow_weekend: bool) -> None:
    """Background worker for the manual full-market shareholder backfill.

    Reuses the job registry's ``_run_shareholders_all`` so the daily job
    and the manual trigger share identical logic; live progress is written
    into ``_SHAREHOLDER_BACKFILL_STATE``.
    """
    from core.database import get_session

    from brsapi.jobs.registry import get_brsapi_job_registry
    from brsapi.services.sync_service import BrsApiSyncService

    state = _SHAREHOLDER_BACKFILL_STATE
    try:
        client = await get_client()
        registry = get_brsapi_job_registry()
        async for session in get_session():
            service = BrsApiSyncService(client=client, session=session)
            report = await registry._run_shareholders_all(
                session,
                service,
                max_symbols=max_symbols,
                allow_weekend=allow_weekend,
                progress=state,
            )
            if report is None:
                state["status"] = "error"
                state["error"] = "هیچ نمادی برای بکفیل پیدا نشد"
            elif state["status"] == "running" and report.skipped and report.items_count == 0:
                # Weekend guard (allow_weekend=false) or market closed
                # (empty AllSymbols) — clean skip, not an error. The registry
                # sets a specific message per case; fall back otherwise.
                state["status"] = "done"
                state["message"] = state.get("message") or "بکفیل اجرا نشد — روز آخر هفته تهران"
            break
    except Exception as exc:
        logger.exception("Manual shareholder backfill failed")
        state["status"] = "error"
        state["error"] = str(exc)
    finally:
        state["finished_at"] = datetime.now().isoformat()
        if state["status"] == "running":
            state["status"] = "error"
            state["error"] = state.get("error") or "بکفیل به‌طور غیرمنتظره متوقف شد"


@router.post(
    "/manage/sync-all-shareholders",
    summary="Download latest shareholders for ALL symbols (manual)",
    description="Trigger a full-market shareholder backfill in the background: AllSymbols + latest shareholder composition for every symbol",
)
async def sync_all_shareholders(
    max_symbols: int = Query(0, ge=0, le=2000, description="Max symbols (0 = all symbols)"),
    allow_weekend: bool = Query(True, description="Allow the run even on Tehran weekends (manual override)"),
) -> ApiResponse[dict[str, Any]]:
    """
    Start a background download of the latest shareholder composition for
    the whole market.

    The run is rate-limited to 2 req/10s by the API, so a full market
    (~1,900 symbols) takes about two hours. Poll
    ``/manage/sync-all-shareholders/status`` for live progress, or use
    ``/manage/sync-all-shareholders/cancel`` to stop it.
    """
    global _shareholder_backfill_task

    if _SHAREHOLDER_BACKFILL_STATE["status"] == "running":
        return ApiResponse[dict[str, Any]](success=False, data={
            "started": False,
            "status": "running",
            "message": "یک بکفیل سهامداران در حال اجراست — پس از اتمام آن دوباره تلاش کنید",
        })

    _SHAREHOLDER_BACKFILL_STATE.update({
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "total_symbols": 0,
        "processed": 0,
        "ok": 0,
        "fail": 0,
        "items": 0,
        "current_symbol": None,
        "cancel_requested": False,
        "message": "در حال راه‌اندازی...",
        "error": None,
    })
    _shareholder_backfill_task = asyncio.create_task(
        _run_shareholder_backfill(max_symbols, allow_weekend)
    )
    return ApiResponse[dict[str, Any]](success=True, data={
        "started": True,
        "status": "running",
        "max_symbols": max_symbols if max_symbols > 0 else "all",
        "message": "بکفیل سهامداران همه نمادها شروع شد — پیشرفت را از همین صفحه پیگیری کنید",
    })


@router.get("/manage/sync-all-shareholders/status", summary="Status of the manual shareholder backfill")
async def sync_all_shareholders_status() -> ApiResponse[dict[str, Any]]:
    """Return live progress of the manual full-market shareholder backfill."""
    return ApiResponse[dict[str, Any]](success=True, data=dict(_SHAREHOLDER_BACKFILL_STATE))


@router.post("/manage/sync-all-shareholders/cancel", summary="Cancel the manual shareholder backfill")
async def cancel_sync_all_shareholders() -> ApiResponse[dict[str, Any]]:
    """Request cancellation of the running backfill (stops after the current symbol)."""
    if _SHAREHOLDER_BACKFILL_STATE["status"] != "running":
        return ApiResponse[dict[str, Any]](success=False, data={
            "cancelled": False,
            "message": "هیچ بکفیلی در حال اجرا نیست",
        })
    _SHAREHOLDER_BACKFILL_STATE["cancel_requested"] = True
    return ApiResponse[dict[str, Any]](success=True, data={
        "cancelled": True,
        "message": "لغو درخواست شد — پس از نماد جاری متوقف می‌شود",
    })


# ── Manual full-market history backfills (admin-triggered) ──────────
# Same background-task pattern as the candlestick/shareholder backfills.
# One request per symbol (~1,900 symbols × 5s spacing ≈ 2.5 hours), so the
# run happens as a background task whose live state is polled by the UI.


def _make_backfill_state() -> dict[str, Any]:
    """Fresh idle state for a manual full-market backfill."""
    return {
        "status": "idle",      # idle | running | done | cancelled | error
        "started_at": None,
        "finished_at": None,
        "total_symbols": 0,
        "processed": 0,
        "ok": 0,
        "fail": 0,
        "items": 0,
        "current_symbol": None,
        "message": None,
        "error": None,
        "cancel_requested": False,
    }


_HISTORY_PRICE_BACKFILL_STATE: dict[str, Any] = _make_backfill_state()
_history_price_backfill_task: asyncio.Task | None = None

_HISTORY_REAL_LEGAL_BACKFILL_STATE: dict[str, Any] = _make_backfill_state()
_history_real_legal_backfill_task: asyncio.Task | None = None


async def _run_history_price_backfill(max_symbols: int, allow_weekend: bool) -> None:
    """Background worker for the manual full-market history-price backfill."""
    from core.database import get_session

    from brsapi.jobs.registry import get_brsapi_job_registry
    from brsapi.services.sync_service import BrsApiSyncService

    state = _HISTORY_PRICE_BACKFILL_STATE
    try:
        client = await get_client()
        registry = get_brsapi_job_registry()
        async for session in get_session():
            service = BrsApiSyncService(client=client, session=session)
            report = await registry._run_history_price_all(
                session,
                service,
                max_symbols=max_symbols,
                allow_weekend=allow_weekend,
                progress=state,
            )
            if report is None:
                state["status"] = "error"
                state["error"] = "هیچ نمادی برای بکفیل پیدا نشد"
            elif state["status"] == "running" and report.skipped and report.items_count == 0:
                # Weekend guard (allow_weekend=false) or market closed
                # (empty AllSymbols) — clean skip, not an error. The registry
                # sets a specific message per case; fall back otherwise.
                state["status"] = "done"
                state["message"] = state.get("message") or "بکفیل اجرا نشد — روز آخر هفته تهران"
            break
    except Exception as exc:
        logger.exception("Manual history-price backfill failed")
        state["status"] = "error"
        state["error"] = str(exc)
    finally:
        state["finished_at"] = datetime.now().isoformat()
        if state["status"] == "running":
            state["status"] = "error"
            state["error"] = state.get("error") or "بکفیل به‌طور غیرمنتظره متوقف شد"


async def _run_history_real_legal_backfill(max_symbols: int, allow_weekend: bool) -> None:
    """Background worker for the manual full-market history real/legal backfill."""
    from core.database import get_session

    from brsapi.jobs.registry import get_brsapi_job_registry
    from brsapi.services.sync_service import BrsApiSyncService

    state = _HISTORY_REAL_LEGAL_BACKFILL_STATE
    try:
        client = await get_client()
        registry = get_brsapi_job_registry()
        async for session in get_session():
            service = BrsApiSyncService(client=client, session=session)
            report = await registry._run_history_real_legal_all(
                session,
                service,
                max_symbols=max_symbols,
                allow_weekend=allow_weekend,
                progress=state,
            )
            if report is None:
                state["status"] = "error"
                state["error"] = "هیچ نمادی برای بکفیل پیدا نشد"
            elif state["status"] == "running" and report.skipped and report.items_count == 0:
                state["status"] = "done"
                state["message"] = state.get("message") or "بکفیل اجرا نشد — روز آخر هفته تهران"
            break
    except Exception as exc:
        logger.exception("Manual history-real-legal backfill failed")
        state["status"] = "error"
        state["error"] = str(exc)
    finally:
        state["finished_at"] = datetime.now().isoformat()
        if state["status"] == "running":
            state["status"] = "error"
            state["error"] = state.get("error") or "بکفیل به‌طور غیرمنتظره متوقف شد"


@router.post(
    "/manage/sync-all-history-price",
    summary="Download daily historical prices for ALL symbols (manual)",
    description="Trigger a full-market history-price backfill in the background: AllSymbols + daily historical prices for every symbol",
)
async def sync_all_history_price(
    max_symbols: int = Query(0, ge=0, le=2000, description="Max symbols (0 = all symbols)"),
    allow_weekend: bool = Query(True, description="Allow the run even on Tehran weekends (manual override)"),
) -> ApiResponse[dict[str, Any]]:
    """
    Start a background download of daily historical prices for the whole market.

    Poll ``/manage/sync-all-history-price/status`` for live progress, or use
    ``/manage/sync-all-history-price/cancel`` to stop it.
    """
    global _history_price_backfill_task

    if _HISTORY_PRICE_BACKFILL_STATE["status"] == "running":
        return ApiResponse[dict[str, Any]](success=False, data={
            "started": False,
            "status": "running",
            "message": "یک بکفیل تاریخچه قیمت در حال اجراست — پس از اتمام آن دوباره تلاش کنید",
        })

    _HISTORY_PRICE_BACKFILL_STATE.update({
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "total_symbols": 0,
        "processed": 0,
        "ok": 0,
        "fail": 0,
        "items": 0,
        "current_symbol": None,
        "cancel_requested": False,
        "message": "در حال راه‌اندازی...",
        "error": None,
    })
    _history_price_backfill_task = asyncio.create_task(
        _run_history_price_backfill(max_symbols, allow_weekend)
    )
    return ApiResponse[dict[str, Any]](success=True, data={
        "started": True,
        "status": "running",
        "max_symbols": max_symbols if max_symbols > 0 else "all",
        "message": "بکفیل تاریخچه قیمت همه نمادها شروع شد — پیشرفت را از همین صفحه پیگیری کنید",
    })


@router.get("/manage/sync-all-history-price/status", summary="Status of the manual history-price backfill")
async def sync_all_history_price_status() -> ApiResponse[dict[str, Any]]:
    """Return live progress of the manual history-price backfill."""
    return ApiResponse[dict[str, Any]](success=True, data=dict(_HISTORY_PRICE_BACKFILL_STATE))


@router.post("/manage/sync-all-history-price/cancel", summary="Cancel the manual history-price backfill")
async def cancel_sync_all_history_price() -> ApiResponse[dict[str, Any]]:
    """Request cancellation of the running backfill (stops after the current symbol)."""
    if _HISTORY_PRICE_BACKFILL_STATE["status"] != "running":
        return ApiResponse[dict[str, Any]](success=False, data={
            "cancelled": False,
            "message": "هیچ بکفیلی در حال اجرا نیست",
        })
    _HISTORY_PRICE_BACKFILL_STATE["cancel_requested"] = True
    return ApiResponse[dict[str, Any]](success=True, data={
        "cancelled": True,
        "message": "لغو درخواست شد — پس از نماد جاری متوقف می‌شود",
    })


@router.post(
    "/manage/sync-all-history-real-legal",
    summary="Download real/legal history for ALL symbols (manual)",
    description="Trigger a full-market real/legal backfill in the background: AllSymbols + real/legal buy-sell history for every symbol",
)
async def sync_all_history_real_legal(
    max_symbols: int = Query(0, ge=0, le=2000, description="Max symbols (0 = all symbols)"),
    allow_weekend: bool = Query(True, description="Allow the run even on Tehran weekends (manual override)"),
) -> ApiResponse[dict[str, Any]]:
    """
    Start a background download of the real/legal history for the whole market.

    Poll ``/manage/sync-all-history-real-legal/status`` for live progress, or
    use ``/manage/sync-all-history-real-legal/cancel`` to stop it.
    """
    global _history_real_legal_backfill_task

    if _HISTORY_REAL_LEGAL_BACKFILL_STATE["status"] == "running":
        return ApiResponse[dict[str, Any]](success=False, data={
            "started": False,
            "status": "running",
            "message": "یک بکفیل حقیقی/حقوقی در حال اجراست — پس از اتمام آن دوباره تلاش کنید",
        })

    _HISTORY_REAL_LEGAL_BACKFILL_STATE.update({
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "total_symbols": 0,
        "processed": 0,
        "ok": 0,
        "fail": 0,
        "items": 0,
        "current_symbol": None,
        "cancel_requested": False,
        "message": "در حال راه‌اندازی...",
        "error": None,
    })
    _history_real_legal_backfill_task = asyncio.create_task(
        _run_history_real_legal_backfill(max_symbols, allow_weekend)
    )
    return ApiResponse[dict[str, Any]](success=True, data={
        "started": True,
        "status": "running",
        "max_symbols": max_symbols if max_symbols > 0 else "all",
        "message": "بکفیل حقیقی/حقوقی همه نمادها شروع شد — پیشرفت را از همین صفحه پیگیری کنید",
    })


@router.get("/manage/sync-all-history-real-legal/status", summary="Status of the manual history real/legal backfill")
async def sync_all_history_real_legal_status() -> ApiResponse[dict[str, Any]]:
    """Return live progress of the manual history real/legal backfill."""
    return ApiResponse[dict[str, Any]](success=True, data=dict(_HISTORY_REAL_LEGAL_BACKFILL_STATE))


@router.post("/manage/sync-all-history-real-legal/cancel", summary="Cancel the manual history real/legal backfill")
async def cancel_sync_all_history_real_legal() -> ApiResponse[dict[str, Any]]:
    """Request cancellation of the running backfill (stops after the current symbol)."""
    if _HISTORY_REAL_LEGAL_BACKFILL_STATE["status"] != "running":
        return ApiResponse[dict[str, Any]](success=False, data={
            "cancelled": False,
            "message": "هیچ بکفیلی در حال اجرا نیست",
        })
    _HISTORY_REAL_LEGAL_BACKFILL_STATE["cancel_requested"] = True
    return ApiResponse[dict[str, Any]](success=True, data={
        "cancelled": True,
        "message": "لغو درخواست شد — پس از نماد جاری متوقف می‌شود",
    })


@router.post("/manage/test-connection", summary="Test BrsApi API key and connectivity")
async def test_brsapi_connection() -> ApiResponse[dict[str, Any]]:
    """
    Verify the configured BrsApi API key by calling a live endpoint.

    Makes a single lightweight request to AllSymbols.php and reports
    whether the key is accepted, the HTTP status, latency, and how many
    symbols were returned.
    """
    import time as _time

    from brsapi.config import settings as _brsapi_settings

    key = _brsapi_settings.api_key
    masked = _mask_api_key(key)
    if not key:
        return ApiResponse[dict[str, Any]](success=False, data={
            "configured": False,
            "key": masked,
            "reachable": False,
            "message": "کلید API تنظیم نشده است — BRSAPI_API_KEY را در فایل .env قرار دهید",
        })

    try:
        client = await get_client()
        start = _time.monotonic()
        result = await client.fetch(BrsApiEndpoints.ALL_SYMBOLS)
        elapsed_ms = round((_time.monotonic() - start) * 1000, 1)

        if not result.success:
            return ApiResponse[dict[str, Any]](success=False, data={
                "configured": True,
                "key": masked,
                "reachable": False,
                "http_status": None,
                "elapsed_ms": elapsed_ms,
                "message": f"اتصال برقرار نشد: {result.error}",
            })

        resp = result.value
        count = _count_payload(resp.data)
        return ApiResponse[dict[str, Any]](success=True, data={
            "configured": True,
            "key": masked,
            "reachable": True,
            "http_status": resp.status_code,
            "elapsed_ms": elapsed_ms,
            "symbols_count": count,
            "message": f"اتصال موفق — {count} نماد از AllSymbols دریافت شد",
        })
    except Exception as exc:
        logger.exception("BrsApi connection test failed")
        return ApiResponse[dict[str, Any]](success=False, data={
            "configured": True,
            "key": masked,
            "reachable": False,
            "message": f"خطا در تست اتصال: {exc}",
        })


@router.get("/manage/sync-stats", summary="Per-endpoint sync status dashboard")
async def sync_stats(
    window_days: int = Query(7, ge=1, le=90, description="Days to look back for error rate and avg duration"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """
    Return per-endpoint sync statistics: freshness, error rate, and avg duration.

    Computes for each endpoint that has sync logs in the given window:
    - last_success_at / last_run_at
    - error_rate (percentage of failed syncs)
    - avg_duration_ms
    - total_runs, success_count, error_count

    Also merges with the static SECTIONS registry so endpoints that have
    never run still appear with empty/null metrics.
    """
    from datetime import datetime

    sync_repo = SyncLogRepository(session)
    stats_rows = await sync_repo.get_sync_stats(window_days=window_days)

    stats_by_endpoint: dict[str, dict[str, Any]] = {}
    for row in stats_rows:
        stats_by_endpoint[row["endpoint"]] = {
            "endpoint": row["endpoint"],
            "last_success_at": str(row["last_success_at"]) if row["last_success_at"] else None,
            "last_run_at": str(row["last_run_at"]) if row["last_run_at"] else None,
            "error_rate": round(float(row["error_rate"]), 2) if row["error_rate"] is not None else 0.0,
            "avg_duration_ms": round(float(row["avg_duration_ms"]), 2) if row["avg_duration_ms"] is not None else 0.0,
            "total_runs": int(row["total_runs"]) if row["total_runs"] else 0,
            "success_count": int(row["success_count"]) if row["success_count"] else 0,
            "error_count": int(row["error_count"]) if row["error_count"] else 0,
        }

    # Merge with static SECTIONS registry so endpoints that have never
    # run still appear in the dashboard.
    endpoint_to_section: dict[str, dict[str, Any]] = {}
    for section_id, cfg in SECTIONS.items():
        ep = cfg["endpoint"].path
        endpoint_to_section.setdefault(ep, {
            "section_id": section_id,
            "name": cfg["name"],
            "name_en": cfg["name_en"],
            "icon": cfg["icon"],
            "category": cfg["category"],
        })

    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    # First, output entries that have stats, enriched with section metadata.
    for ep, stat in stats_by_endpoint.items():
        meta = endpoint_to_section.get(ep, {})
        seen.add(ep)
        result.append({
            **stat,
            "section_id": meta.get("section_id"),
            "name": meta.get("name"),
            "name_en": meta.get("name_en"),
            "icon": meta.get("icon"),
            "category": meta.get("category", "other"),
        })

    # Then, output registered sections that have never produced a sync log.
    for ep, meta in endpoint_to_section.items():
        if ep in seen:
            continue
        result.append({
            "endpoint": ep,
            "section_id": meta["section_id"],
            "name": meta["name"],
            "name_en": meta["name_en"],
            "icon": meta["icon"],
            "category": meta["category"],
            "last_success_at": None,
            "last_run_at": None,
            "error_rate": 0.0,
            "avg_duration_ms": 0.0,
            "total_runs": 0,
            "success_count": 0,
            "error_count": 0,
        })

    # Overall summary
    now = datetime.now()
    total_runs = sum(s["total_runs"] for s in result)
    total_errors = sum(s["error_count"] for s in result)
    never_synced = sum(1 for s in result if s["total_runs"] == 0)
    stale_count = sum(
        1 for s in result
        if s["last_success_at"] is None or
        (now - datetime.fromisoformat(s["last_success_at"])).total_seconds() > 24 * 3600
    )

    return ApiResponse[dict[str, Any]](success=True, data={
        "window_days": window_days,
        "endpoints": result,
        "summary": {
            "total_endpoints": len(result),
            "total_runs": total_runs,
            "total_errors": total_errors,
            "never_synced": never_synced,
            "stale_endpoints": stale_count,
            "overall_error_rate": round((total_errors / total_runs) * 100, 2) if total_runs else 0.0,
        },
    })


# Frontend sync-dashboard keys → (SECTIONS id, default max-age in minutes).
# The frontend (SyncStatus widget, /admin, /sync, /sync-manager) reads this
# endpoint to render freshness per section + the "Sync now" buttons.
#
# Note: gold-coin and currency both fetch the combined /Market/Gold_Currency.php
# payload, so they share one sync-log endpoint key — their freshness values
# will always be identical (correct: a single fetch refreshes both).
_SYNC_STATUS_SECTIONS: dict[str, tuple[str, int]] = {
    "symbols":     ("all-symbols", 10),
    "commodities": ("commodity", 10),
    "gold_coin":   ("gold-coin", 10),
    "currency":    ("currency", 10),
    "crypto":      ("crypto", 10),
    "index":       ("index-tse", 10),
    "ime_futures": ("ime-futures", 30),
    "ime_options": ("ime-options", 30),
    "options":     ("option", 30),
    "codal":       ("codal", 60),
}


@router.get("/sync-status", summary="Sync freshness status for the frontend")
async def sync_status(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Return per-section freshness for the frontend sync dashboard.

    Each entry carries the record count, the last successful sync time, the
    data age in minutes, and a freshness status derived from the default
    max-age threshold for that section.
    """
    sync_repo = SyncLogRepository(session)

    # Row estimates from pg_stat for fast approximate counts
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

    result: dict[str, Any] = {}
    for key, (section_id, max_age_minutes) in _SYNC_STATUS_SECTIONS.items():
        entry: dict[str, Any] = {
            "last_fetched": None,
            "record_count": 0,
            "age_minutes": None,
            "status": "unknown",
            "max_age_minutes": max_age_minutes,
        }
        cfg = SECTIONS.get(section_id)
        if cfg is None:
            result[key] = entry
            continue
        try:
            model = cfg["model"]
            table_name = model.__tablename__
            count = pg_stat_counts.get(table_name)
            if count is None:
                try:
                    cnt = await session.execute(select(sa_func.count()).select_from(model))
                    count = cnt.scalar() or 0
                except Exception as exc:
                    # A missing table would otherwise surface as a silent
                    # "missing" status — log so it is diagnosable.
                    logger.debug("sync_status count fallback failed for %s: %s", table_name, exc)
                    count = 0
            entry["record_count"] = int(count or 0)

            last = await sync_repo.last_sync(cfg["endpoint"].path, max_age_seconds=999999999)
            if last and last.completed_at:
                entry["last_fetched"] = last.completed_at.isoformat()
                entry["age_minutes"] = round(
                    max(0.0, (datetime.now() - last.completed_at).total_seconds() / 60), 1
                )
        except Exception as exc:
            logger.warning("sync_status failed for %s: %s", section_id, exc)
            entry["status"] = "error"
            entry["error"] = str(exc)
            result[key] = entry
            continue

        # Derive freshness: missing → no data; stale/outdated from age.
        if entry["record_count"] == 0:
            entry["status"] = "missing"
        elif entry["last_fetched"] is None or entry["age_minutes"] is None:
            entry["status"] = "unknown"
        elif entry["age_minutes"] <= max_age_minutes:
            entry["status"] = "ok"
        elif entry["age_minutes"] <= max_age_minutes * 3:
            entry["status"] = "stale"
        else:
            entry["status"] = "outdated"
        result[key] = entry

    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.get("/sync-history", summary="Recent BrsApi sync history")
async def sync_history(
    hours: int = Query(24, ge=1, le=24 * 30, description="Look-back window in hours"),
    limit: int = Query(300, ge=1, le=1000, description="Max entries"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[dict[str, Any]]]:
    """Return recent sync-log entries for the sync dashboard history list."""
    from datetime import timedelta

    from brsapi.models.base import SyncLogModel

    cutoff = datetime.now() - timedelta(hours=hours)
    stmt = (
        select(SyncLogModel)
        .where(SyncLogModel.completed_at >= cutoff)
        .order_by(SyncLogModel.completed_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    items: list[dict[str, Any]] = []
    for r in rows:
        ts = r.started_at or r.completed_at
        items.append({
            "time": ts.isoformat() if ts else None,
            "endpoint": r.endpoint,
            "category": r.category,
            "status": r.status,
            "items_count": r.items_count,
            "duration_ms": r.duration_ms,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "error_message": r.error_message,
        })

    return ApiResponse[list[dict[str, Any]]](success=True, data=items)


@router.get("/nav-sync-status", summary="NAV sync status (latest date, success/fail, today's symbols)")
async def nav_sync_status(
    days: int = Query(7, ge=1, le=90, description="Look-back window (days) for sync-log counts"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Return a focused status report for the NAV sync pipeline.

    Aggregates three views:
      - **Data**: latest NAV date in ``brsapi_nav_records``, distinct symbols,
        and the symbols that already hold today's (Jalali) NAV record.
      - **Sync health**: success/error counts, error rate and average duration
        from ``brsapi_sync_log`` for the NAV endpoint over the last ``days``.
      - **Coverage**: how many fund symbols are known vs how many hold NAV.

    This is the endpoint the frontend sync dashboard should read to answer
    "is today's NAV in yet?" and "did the last run mostly succeed?".
    """
    import jdatetime

    from brsapi.models.base import SyncLogModel
    from brsapi.services.sync_service import BrsApiSyncService

    nav_path = BrsApiEndpoints.NAV.path

    # ── 1) Data view (brsapi_nav_records) ───────────────────────────
    latest_date: str | None = None
    distinct_symbols = 0
    today_jalali = jdatetime.date.today().strftime("%Y-%m-%d")
    today_symbols: list[str] = []
    total_records = 0
    try:
        r = await session.execute(select(sa_func.max(NavRecordModel.date)))
        latest_date = r.scalar()
        r = await session.execute(select(sa_func.count(sa_func.distinct(NavRecordModel.symbol))))
        distinct_symbols = int(r.scalar() or 0)
        r = await session.execute(select(sa_func.count()).select_from(NavRecordModel))
        total_records = int(r.scalar() or 0)
        r = await session.execute(
            select(NavRecordModel.symbol)
            .where(NavRecordModel.date == today_jalali)
            .distinct()
            .order_by(NavRecordModel.symbol)
        )
        today_symbols = [row[0] for row in r if row[0]]
    except Exception as exc:
        logger.warning("nav-sync-status data query failed: %s", exc)

    # ── 2) Sync health (brsapi_sync_log) ────────────────────────────
    sync_stats: dict[str, Any] = {
        "last_run_at": None,
        "last_success_at": None,
        "total_runs": 0,
        "success_count": 0,
        "error_count": 0,
        "error_rate": 0.0,
        "avg_duration_ms": 0.0,
        "recent_errors": [],
    }
    try:
        from datetime import timedelta

        # Reuse the repository aggregator for the window metrics.
        from brsapi.repositories import SyncLogRepository

        sync_repo = SyncLogRepository(session)
        rows = await sync_repo.get_sync_stats(endpoint=nav_path, window_days=days)
        if rows:
            s = rows[0]
            sync_stats["last_run_at"] = str(s["last_run_at"]) if s.get("last_run_at") else None
            sync_stats["last_success_at"] = str(s["last_success_at"]) if s.get("last_success_at") else None
            sync_stats["total_runs"] = int(s.get("total_runs") or 0)
            sync_stats["success_count"] = int(s.get("success_count") or 0)
            sync_stats["error_count"] = int(s.get("error_count") or 0)
            sync_stats["error_rate"] = round(float(s.get("error_rate") or 0.0), 1)
            sync_stats["avg_duration_ms"] = round(float(s.get("avg_duration_ms") or 0.0), 1)

        # Recent error details (the aggregator doesn't return messages).
        cutoff = datetime.now() - timedelta(days=days)
        err_stmt = (
            select(SyncLogModel)
            .where(
                SyncLogModel.endpoint == nav_path,
                SyncLogModel.started_at >= cutoff,
                SyncLogModel.status == "error",
            )
            .order_by(SyncLogModel.completed_at.desc().nullslast())
            .limit(5)
        )
        err_rows = (await session.execute(err_stmt)).scalars().all()
        sync_stats["recent_errors"] = [
            {
                "at": (r.completed_at or r.started_at).isoformat()
                if (r.completed_at or r.started_at) else None,
                "message": (r.error_message or "")[:200],
            }
            for r in err_rows
        ]
    except Exception as exc:
        logger.warning("nav-sync-status sync-log query failed: %s", exc)

    # ── 3) Coverage (known fund symbols vs with NAV) ─────────────────
    coverage: dict[str, Any] = {
        "total_fund_symbols": 0,
        "with_nav": distinct_symbols,
        "missing": 0,
        "coverage_pct": 0.0,
    }
    try:
        # DB-only query — no HTTP client needed.
        fund_syms = await BrsApiSyncService()._get_fund_symbols(session)
        coverage["total_fund_symbols"] = len(fund_syms)
        coverage["missing"] = max(0, len(fund_syms) - distinct_symbols)
        if fund_syms:
            coverage["coverage_pct"] = round(
                (distinct_symbols / len(fund_syms)) * 100, 1
            )
    except Exception as exc:
        logger.warning("nav-sync-status coverage query failed: %s", exc)

    return ApiResponse[dict[str, Any]](success=True, data={
        "endpoint": nav_path,
        "data": {
            "total_records": total_records,
            "distinct_symbols": distinct_symbols,
            "latest_date": latest_date,
            "today_jalali": today_jalali,
            "today_record_count": len(today_symbols),
            "today_symbols": today_symbols,
        },
        "sync": sync_stats,
        "coverage": coverage,
        "window_days": days,
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


# ── History Fetch from BrsApi (Crypto / Gold / Currency) ──────────────


@router.get("/manage/history-status", summary="Status of history tables")
async def history_status(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Check row counts for all history tables."""
    tables = {
        "brsapi_crypto_daily_history": "Crypto",
        "brsapi_gold_coin_history": "Gold/Coins",
        "brsapi_gold_currency_pro_daily_history": "Currency/XAUUSD",
    }
    result: dict[str, Any] = {}
    for table, label in tables.items():
        try:
            r = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = r.scalar() or 0
            r2 = await session.execute(text(f"SELECT MIN(date), MAX(date), COUNT(DISTINCT symbol) FROM {table}"))
            row = r2.fetchone()
            result[label] = {
                "table": table,
                "rows": count,
                "min_date": row[0] if row else None,
                "max_date": row[1] if row else None,
                "symbols": row[2] if row else 0,
            }
        except Exception as e:
            logger.exception("Failed to get history status for %s", label)
            result[label] = {"table": table, "rows": 0, "error": str(e)}
    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.post("/manage/sync-crypto-history", summary="Fetch crypto history from BrsApi")
async def sync_crypto_history(
    limit: int = Query(0, ge=0, le=500, description="Max symbols (0 = all)"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Fetch historical daily crypto data from BrsApi.ir and store in DB."""
    from brsapi.services.history_fetch_service import HistoryFetchService

    svc = HistoryFetchService(session=session)
    reports = await svc.sync_crypto_history(limit=limit)

    total_rows = sum(r.record_count for r in reports)
    success = sum(1 for r in reports if r.success)
    fail = sum(1 for r in reports if not r.success)
    total_ms = sum(r.duration_ms for r in reports)

    return ApiResponse[dict[str, Any]](success=True, data={
        "total_symbols": len(reports),
        "success": success,
        "failed": fail,
        "total_rows": total_rows,
        "duration_ms": round(total_ms, 1),
        "results": [
            {"symbol": r.symbol, "rows": r.record_count, "success": r.success,
             "error": r.error, "duration_ms": round(r.duration_ms, 1)}
            for r in reports[:50]
        ],
    })


@router.post("/manage/sync-gold-currency-history", summary="Fetch gold/currency history from BrsApi")
async def sync_gold_currency_history(
    limit: int = Query(0, ge=0, le=500, description="Max symbols (0 = all)"),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Fetch historical daily gold/currency data from BrsApi.ir and store in DB."""
    from brsapi.services.history_fetch_service import HistoryFetchService

    svc = HistoryFetchService(session=session)
    reports = await svc.sync_gold_currency_history(limit=limit)

    total_rows = sum(r.record_count for r in reports)
    success = sum(1 for r in reports if r.success)
    fail = sum(1 for r in reports if not r.success)
    total_ms = sum(r.duration_ms for r in reports)

    return ApiResponse[dict[str, Any]](success=True, data={
        "total_symbols": len(reports),
        "success": success,
        "failed": fail,
        "total_rows": total_rows,
        "duration_ms": round(total_ms, 1),
        "results": [
            {"symbol": r.symbol, "rows": r.record_count, "success": r.success,
             "error": r.error, "duration_ms": round(r.duration_ms, 1)}
            for r in reports[:50]
        ],
    })


@router.post("/manage/import-json-history", summary="Import JSON files into history tables")
async def import_json_history(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Read crypto_history/ and history_data/ JSON files and insert into DB."""
    import json as _json
    import time as _time
    from pathlib import Path

    t0 = _time.time()
    total_inserted = 0
    total_skipped = 0
    files_count = 0

    CRYPTO_DIR = Path("crypto_history")
    HISTORY_DIR = Path("history_data")
    CRYPTO_TABLE = "brsapi_crypto_daily_history"
    GOLD_TABLE = "brsapi_gold_coin_history"
    CURRENCY_TABLE = "brsapi_gold_currency_pro_daily_history"

    GOLD_SYMBOLS = {
        "IR_GOLD_18K", "IR_GOLD_24K", "IR_GOLD_MELTED",
        "IR_COIN_1G", "IR_COIN_BAHAR", "IR_COIN_EMAMI",
        "IR_COIN_HALF", "IR_COIN_QUARTER",
    }
    GOLD_SYMBOLS.update({f"IR_PCOIN_{s}" for s in [
        "1-1G", "1-2G", "1-3G", "1-4G", "1-5G",
        "100MG", "1G", "200MG", "300MG", "400MG",
        "500MG", "600MG", "700MG", "800MG", "900MG",
    ]})

    def _num(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).replace(",", "").replace("٬", "").strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    async def _import_file(filepath: Path, table: str) -> tuple[int, int]:
        symbol = filepath.stem.replace("_history", "")
        with open(filepath, encoding="utf-8") as f:
            data = _json.load(f)
        if not data:
            return 0, 0
        inserted = 0
        skipped = 0
        for item in data:
            date = str(item.get("date", "")).replace("/", "-")
            if not date:
                skipped += 1
                continue
            o = _num(item.get("open"))
            h = _num(item.get("high"))
            lo = _num(item.get("low"))
            c = _num(item.get("close"))
            v = _num(item.get("volume"))
            if c is None or c <= 0:
                skipped += 1
                continue
            try:
                if table == CRYPTO_TABLE:
                    await session.execute(text(f"""
                        INSERT INTO {table} (symbol, date, price_open, price_high, price_low, price_close, volume)
                        VALUES (:sym, :date, :o, :h, :l, :c, :v)
                        ON CONFLICT (symbol, date) DO UPDATE SET
                            price_open = EXCLUDED.price_open, price_high = EXCLUDED.price_high,
                            price_low = EXCLUDED.price_low, price_close = EXCLUDED.price_close, volume = EXCLUDED.volume
                    """), {"sym": symbol, "date": date, "o": o, "h": h, "l": lo, "c": c, "v": v})
                else:
                    await session.execute(text(f"""
                        INSERT INTO {table} (symbol, date, price_open, price_high, price_low, price_close)
                        VALUES (:sym, :date, :o, :h, :l, :c)
                        ON CONFLICT (symbol, date) DO UPDATE SET
                            price_open = EXCLUDED.price_open, price_high = EXCLUDED.price_high,
                            price_low = EXCLUDED.price_low, price_close = EXCLUDED.price_close
                    """), {"sym": symbol, "date": date, "o": o, "h": h, "l": lo, "c": c})
                inserted += 1
            except Exception:
                skipped += 1
        await session.commit()
        return inserted, skipped

    if CRYPTO_DIR.exists():
        for fp in sorted(CRYPTO_DIR.glob("*.json")):
            ins, skip = await _import_file(fp, CRYPTO_TABLE)
            total_inserted += ins
            total_skipped += skip
            files_count += 1

    if HISTORY_DIR.exists():
        for fp in sorted(HISTORY_DIR.glob("*.json")):
            symbol = fp.stem.replace("_history", "")
            table = GOLD_TABLE if symbol in GOLD_SYMBOLS else CURRENCY_TABLE
            ins, skip = await _import_file(fp, table)
            total_inserted += ins
            total_skipped += skip
            files_count += 1

    elapsed = _time.time() - t0
    return ApiResponse[dict[str, Any]](success=True, data={
        "total_inserted": total_inserted,
        "total_skipped": total_skipped,
        "files_imported": files_count,
        "duration_s": round(elapsed, 1),
    })


@router.get("/codal/{symbol}", summary="Codal financial data for a symbol")
async def get_codal_data(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """Get codal reports, financial statements, and audit summary for a symbol."""
    import json as _json

    result: dict[str, Any] = {"symbol": symbol}

    # 1. Audit summary (financial metrics)
    try:
        r = await session.execute(text("""
            SELECT revenue, net_profit, total_assets, total_equity, eps,
                   roe, roa, gross_margin, net_margin, current_ratio,
                   debt_to_equity, asset_turnover, revenue_growth, net_profit_growth,
                   health_score, health_classification, forensic_risk,
                   earnings_quality_score, analysis_status
            FROM codal_audit_summary WHERE symbol = :sym LIMIT 1
        """), {"sym": symbol})
        row = r.fetchone()
        if row:
            result["audit"] = {
                "revenue": row[0], "net_profit": row[1], "total_assets": row[2],
                "total_equity": row[3], "eps": row[4], "roe": row[5], "roa": row[6],
                "gross_margin": row[7], "net_margin": row[8], "current_ratio": row[9],
                "debt_to_equity": row[10], "asset_turnover": row[11],
                "revenue_growth": row[12], "net_profit_growth": row[13],
                "health_score": row[14], "health_classification": row[15],
                "forensic_risk": row[16], "earnings_quality_score": row[17],
                "analysis_status": row[18],
            }
    except Exception:
        result["audit"] = None

    # 2. Latest financial statement (parsed_data)
    try:
        r = await session.execute(text("""
            SELECT title, report_type, parsed_data, imported_at
            FROM codal_financial_statements WHERE symbol = :sym
            ORDER BY imported_at DESC LIMIT 1
        """), {"sym": symbol})
        row = r.fetchone()
        if row:
            parsed = row[2]
            if isinstance(parsed, str):
                parsed = _json.loads(parsed)
            result["financial"] = {
                "title": row[0], "report_type": row[1],
                "parsed_data": parsed, "date": safe_row_str(row, idx=3, default=None),
            }
    except Exception:
        result["financial"] = None

    # 3. Recent announcements
    try:
        r = await session.execute(text("""
            SELECT company_name, report_type, period, audit_status, publish_date, summary, attachment_url
            FROM codal_reports WHERE symbol = :sym
            ORDER BY publish_date DESC LIMIT 10
        """), {"sym": symbol})
        result["announcements"] = [
            {
                "company": row[0], "type": row[1], "period": row[2],
                "audit": row[3], "date": row[4], "summary": row[5],
                "url": row[6],
            }
            for row in r.fetchall()
        ]
    except Exception:
        result["announcements"] = []

    # 4. Report type counts
    try:
        r = await session.execute(text("""
            SELECT report_type, COUNT(*) as cnt
            FROM codal_reports WHERE symbol = :sym
            GROUP BY report_type ORDER BY cnt DESC
        """), {"sym": symbol})
        result["report_types"] = {row[0]: row[1] for row in r.fetchall()}
    except Exception:
        result["report_types"] = {}

    return ApiResponse[dict[str, Any]](success=True, data=result)


@router.get("/codal-list", summary="List symbols with codal data")
async def codal_list(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """List all symbols with their codal health score."""
    r = await session.execute(text("""
        SELECT symbol, health_score, health_classification, revenue, roe, net_margin
        FROM codal_audit_summary
        ORDER BY health_score DESC NULLS LAST
    """))
    items = [
        {"symbol": row[0], "health": row[1], "class": row[2],
         "revenue": row[3], "roe": row[4], "margin": row[5]}
        for row in r.fetchall()
    ]
    return ApiResponse[dict[str, Any]](success=True, data={"symbols": items, "total": len(items)})
