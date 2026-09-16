"""
📊 Funds API — داده‌های واقعی صندوق‌های سرمایه‌گذاری بازار ایران

Endpoints:
  GET  /funds                    — لیست همه صندوق‌ها (ترکیب بورس تهران + بورس کالا)
  GET  /funds/types              — لیست انواع صندوق‌ها
  GET  /funds/{symbol}           — جزئیات کامل یک صندوق
  GET  /funds/{symbol}/nav       — تاریخچه NAV (صدور/ابطال + اسنپ‌شات‌های روزانه)
  GET  /funds/{symbol}/analysis  — تحلیل هوشمند ۶‌بعدی
  POST /funds/{symbol}/update    — به‌روزرسانی یک صندوق از اسنپ‌شات‌های BrsApi
  POST /funds/sync-all           — همگام‌سازی انبوه صندوق‌ها

منابع داده (همگی واقعی و از دیتابیس):
  - جدول ``funds``                 → صندوق‌های بورس تهران (قیمت/NAV غنی)
  - جدول ``brsapi_ime_funds``      → صندوق‌های کالایی بورس کالا (dedupe شده)
  - جدول ``brsapi_nav_records``    → تاریخچه NAV صدور/ابطال ETFها
"""

from __future__ import annotations

import asyncio
import contextlib
import statistics
import time
from typing import Any

import jdatetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_brsapi_query_service, get_db_session
from apps.api.error_handlers import safe_error_message
from brsapi.constants import BRSAPI_ETF_SYMBOLS
from brsapi.models.ime import ImeFundModel
from brsapi.models.tsetmc import IntradayTradeModel, NavRecordModel, SymbolSnapshotModel
from brsapi.services.query_service import BrsApiQueryService
from core.config import settings
from core.logging import get_logger
from core.time import utc_now_naive
from models.fund import FundModel
from schemas.common.responses import ApiResponse
from services.fund_service import FundService

logger = get_logger(__name__)
router = APIRouter()

# ── In-memory cache for the merged fund list ────────────────────────────────
# brsapi_symbol_snapshots has ~836K rows; the latest-per-symbol query takes
# several seconds, so we cache the merged map with a TTL and refresh it in the
# background (stale-while-revalidate) so the endpoint never blocks on a slow
# rebuild. Snapshots are refreshed every few minutes, so the configured TTL
# (default 120s) keeps data fresh while keeping the endpoint snappy.
_CACHE_TTL_SECONDS = settings.fund_cache_ttl_seconds
_cache_lock = asyncio.Lock()
_cache: dict[str, Any] | None = None
_cache_at: float = 0.0


async def _get_cached_funds(session: AsyncSession) -> dict[str, dict[str, Any]]:
    """Return the merged fund map, rebuilding it in the background on expiry.

    When the cached value is stale we kick off a background rebuild (only one
    at a time via the lock) and serve the previous snapshot immediately, so a
    cold-cache rebuild never stalls the API response.
    """
    global _cache, _cache_at
    now = time.monotonic()
    if _cache is not None and (now - _cache_at) < _CACHE_TTL_SECONDS:
        return _cache
    # Stale or empty — rebuild in background, serve stale while it runs.
    if _cache is not None and _cache_lock.locked():
        return _cache
    async with _cache_lock:
        now = time.monotonic()
        if _cache is not None and (now - _cache_at) < _CACHE_TTL_SECONDS:
            return _cache
        if _cache is not None:
            # Stale value: trigger background refresh, return current data.
            # IMPORTANT: the background task opens its OWN DB session — the
            # request's session must never be shared with a background task,
            # because FastAPI closes it when the request ends, raising
            # IllegalStateChangeError ("close() can't be called here").
            _cache_at = time.monotonic()  # avoid re-triggering on every request
            asyncio.create_task(_rebuild_cache())
            return _cache
        merged = await _load_merged_funds(session)
        _cache = merged
        _cache_at = time.monotonic()
        logger.info("Fund cache built (first time): %d funds", len(merged))
        return merged


async def _rebuild_cache() -> None:
    """Background task: rebuild the merged fund map with its own DB session.

    Never pass a request-scoped session into this task — the request
    dependency closes it as soon as the request returns, which races with the
    in-flight query and raises ``IllegalStateChangeError``.
    """
    try:
        from core.database import async_session_factory

        if async_session_factory is None:
            return
        async with async_session_factory() as session:
            merged = await _load_merged_funds(session)
            async with _cache_lock:
                _cache = merged
                _cache_at = time.monotonic()
                logger.info("Fund cache refreshed in background: %d funds", len(merged))
    except Exception:
        logger.exception("Background fund cache refresh failed")


async def _invalidate_fund_cache() -> None:
    """Clear the in-memory fund cache (call after a fund update/sync)."""
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


def get_fund_service(db_session: AsyncSession = Depends(get_db_session)) -> FundService:
    """Factory dependency for FundService with proper DB session."""
    return FundService(session=db_session)


# ── Fund type inference (Persian names) ─────────────────────────────────────


def _infer_fund_type(name: str | None, symbol: str | None = None) -> str:
    """Infer fund type from its Persian name (rich taxonomy for the overview)."""
    n = (name or "") + " " + (symbol or "")
    # Order matters — most-specific keywords first.
    if "نقره" in n:
        return "نقره"
    if any(k in n for k in ("طلا", "زر")):
        return "طلا"
    if "اهرم" in n:
        return "اهرمی"
    if "تضمین" in n:
        return "تضمین سرمایه"
    if any(k in n for k in ("درآمد", "ثابت", "بازده", "بانک", "اوراق")):
        return "درآمد ثابت"
    if any(k in n for k in ("املاک", "ملک")):
        return "املاک"
    if any(k in n for k in ("کالایی", "کالا")):
        return "کالایی"
    if any(k in n for k in ("فراصندوق", "فرا صندوق", "صندوق‌درصندوق")):
        return "فراصندوق"
    if "خصوصی" in n:
        return "خصوصی"
    if any(k in n for k in ("جسورانه", "خلاق", "خلق")):
        return "جسورانه"
    if any(k in n for k in ("شاخص", "هم‌وزن")):
        return "سهامی شاخصی"
    if any(k in n for k in ("سهام", "سهامی")):
        return "سهامی عادی"
    if any(k in n for k in ("مختلط", "متنوع")):
        return "مختلط"
    if "اختصاصی" in n:
        return "اختصاصی"
    if "بخشی" in n:
        return "بخشی"
    return "سهامی عادی"


# ── Row → unified Fund dict ─────────────────────────────────────────────────


def _ime_fund_to_dict(r: ImeFundModel) -> dict[str, Any]:
    """Convert a brsapi_ime_funds row to the unified Fund shape."""
    nav = r.price_close or r.price_last or 0
    prev = r.price_yesterday or 0
    change_pct = r.price_close_change_pct if r.price_close_change_pct is not None else r.price_last_change_pct
    change = r.price_close_change if r.price_close_change is not None else r.price_last_change
    if change_pct is None and prev and nav:
        change_pct = (nav - prev) / prev * 100
    if change is None and prev and nav:
        change = nav - prev
    return {
        "symbol": r.symbol,
        "name": r.name or r.symbol,
        "isin": r.isin or "",
        "fund_type": _infer_fund_type(r.name, r.symbol),
        "market": "ime",
        "nav": float(nav or 0),
        "nav_change": float(change or 0),
        "nav_change_pct": round(float(change_pct or 0), 2),
        "price_last": float(r.price_last or 0),
        "price_close": float(r.price_close or 0),
        "price_yesterday": float(r.price_yesterday or 0),
        "price_max": float(r.price_max or 0),
        "price_min": float(r.price_min or 0),
        "trade_volume": int(r.trade_volume or 0),
        "trade_value": float(r.trade_value or 0),
        "trade_count": int(r.trade_count or 0),
        "shares_count": int(r.shares_count or 0),
        "base_volume": int(r.base_volume or 0),
        "market_value": float(r.market_value or 0),
        "buy_real_volume": int(r.buy_real_volume or 0),
        "buy_legal_volume": int(r.buy_legal_volume or 0),
        "sell_real_volume": int(r.sell_real_volume or 0),
        "sell_legal_volume": int(r.sell_legal_volume or 0),
        "time": str(r.fetched_at or ""),
        "data_source": "ime",
        "updated_at": str(getattr(r, "fetched_at", "") or ""),
    }


def _snapshot_to_dict(r: SymbolSnapshotModel) -> dict[str, Any]:
    """Convert a ``brsapi_symbol_snapshots`` row (latest TSE ETF snapshot) to the unified Fund shape."""
    nav = r.price_close or r.price_last or 0
    prev = r.price_yesterday or 0
    change_pct = r.price_close_change_pct if r.price_close_change_pct is not None else r.price_last_change_pct
    change = r.price_close_change if r.price_close_change is not None else r.price_last_change
    if change_pct is None and prev and nav:
        change_pct = (nav - prev) / prev * 100
    if change is None and prev and nav:
        change = nav - prev
    return {
        "symbol": r.symbol,
        "name": r.name or r.symbol,
        "isin": r.isin or "",
        "fund_type": _infer_fund_type(r.name, r.symbol),
        "market": "tse",
        "nav": float(nav or 0),
        "nav_change": float(change or 0),
        "nav_change_pct": round(float(change_pct or 0), 2),
        "price_last": float(r.price_last or 0),
        "price_close": float(r.price_close or 0),
        "price_yesterday": float(r.price_yesterday or 0),
        "price_max": float(r.price_max or 0),
        "price_min": float(r.price_min or 0),
        "trade_volume": int(r.trade_volume or 0),
        "trade_value": float(r.trade_value or 0),
        "trade_count": int(r.trade_count or 0),
        "shares_count": int(r.shares_count or 0),
        "base_volume": int(r.base_volume or 0),
        "market_value": float(r.market_value or 0),
        "buy_real_volume": int(r.buy_real_volume or 0),
        "buy_legal_volume": int(r.buy_legal_volume or 0),
        "sell_real_volume": int(r.sell_real_volume or 0),
        "sell_legal_volume": int(r.sell_legal_volume or 0),
        "time": str(r.fetched_at or ""),
        "data_source": "tsetmc",
        "snapshot_date": str(r.fetched_at)[:10] if r.fetched_at else "",
        "updated_at": str(r.fetched_at or ""),
    }


def _fund_model_to_dict(r: FundModel) -> dict[str, Any]:
    """Convert a ``funds`` table row (TSE funds) to the unified Fund shape."""
    return {
        "symbol": r.symbol,
        "name": r.name or r.symbol,
        "isin": r.isin or "",
        "fund_type": r.fund_type or _infer_fund_type(r.name, r.symbol),
        "market": "tse",
        "nav": float(r.nav or 0),
        "nav_change": float(r.nav_change or 0),
        "nav_change_pct": round(float(r.nav_change_pct or 0), 2),
        "price_last": float(r.price_last or 0),
        "price_close": float(r.price_close or 0),
        "price_yesterday": float(r.price_yesterday or 0),
        "price_max": float(r.price_max or 0),
        "price_min": float(r.price_min or 0),
        "trade_volume": int(r.trade_volume or 0),
        "trade_value": float(r.trade_value or 0),
        "trade_count": int(r.trade_count or 0),
        "shares_count": int(r.shares_count or 0),
        "base_volume": int(r.base_volume or 0),
        "market_value": float(r.market_value or 0),
        "buy_real_volume": int(r.buy_real_volume or 0),
        "buy_legal_volume": int(r.buy_legal_volume or 0),
        "sell_real_volume": int(r.sell_real_volume or 0),
        "sell_legal_volume": int(r.sell_legal_volume or 0),
        "time": r.time or "",
        "data_source": r.data_source or "tsetmc",
        "snapshot_date": r.snapshot_date or "",
        "updated_at": str(r.updated_at or r.created_at or ""),
    }


async def _load_merged_funds(session: AsyncSession) -> dict[str, dict[str, Any]]:
    """Merge all real fund sources into one map.

    Sources (priority order, TSE-first):
      1) ``funds`` table                 → صندوق‌های بورس تهران با داده غنی (NAV)
      2) ``brsapi_symbol_snapshots``     → آخرین اسنپ‌شات هر ETF بورس تهران (~۴۷۰ صندوق)
      3) ``brsapi_ime_funds``            → صندوق‌های کالایی بورس کالا (آخرین اسنپ‌شات هر نماد)

    ``funds`` wins on symbol collision because it carries richer NAV fields.
    """
    merged: dict[str, dict[str, Any]] = {}

    # 1) TSE funds table — richest NAV data; wins on collision
    try:
        result = await session.execute(select(FundModel).order_by(FundModel.symbol))
        for row in result.scalars().all():
            merged[row.symbol] = _fund_model_to_dict(row)
    except Exception as e:
        logger.warning("Funds table unavailable: %s", e)

    # 2) IME commodity funds — latest snapshot per symbol. Loaded BEFORE the
    #    ETF snapshots so commodity funds keep their ``ime`` market label even
    #    though they also appear in the TSETMC symbol snapshots.
    try:
        subq = (
            select(ImeFundModel.symbol, func.max(ImeFundModel.id).label("max_id"))
            .group_by(ImeFundModel.symbol)
            .subquery()
        )
        stmt = select(ImeFundModel).join(subq, ImeFundModel.id == subq.c.max_id)
        result = await session.execute(stmt)
        for row in result.scalars().all():
            merged.setdefault(row.symbol, _ime_fund_to_dict(row))
    except Exception as e:
        logger.warning("IME funds table unavailable: %s", e)

    # 3) TSE ETF snapshots — latest snapshot per symbol whose sector is a fund
    #    (صندوق سرمایه‌گذاری قابل معامله) or is a known ETF symbol. This is the
    #    biggest source (~۴۷۰ صندوق بورس تهران) previously ignored by the API.
    try:
        etf_list = list(BRSAPI_ETF_SYMBOLS)
        # Also pull any symbol that has a real NAV record — some fund symbols carry
        # a different sector label and would otherwise never surface their NAV.
        # nav_records unavailable — the plain ETF filter still applies
        with contextlib.suppress(Exception):
            nav_syms = (await session.execute(select(NavRecordModel.symbol).distinct())).scalars().all()
            etf_list = list(dict.fromkeys([*etf_list, *[s for s in nav_syms if s]]))
        fund_sector = "صندوق سرمایه‌گذاری قابل معامله"
        subq = (
            select(SymbolSnapshotModel.symbol, func.max(SymbolSnapshotModel.fetched_at).label("latest"))
            .where((SymbolSnapshotModel.sector == fund_sector) | (SymbolSnapshotModel.symbol.in_(etf_list)))
            .group_by(SymbolSnapshotModel.symbol)
            .subquery()
        )
        stmt = select(SymbolSnapshotModel).join(
            subq, (SymbolSnapshotModel.symbol == subq.c.symbol) & (SymbolSnapshotModel.fetched_at == subq.c.latest)
        )
        result = await session.execute(stmt)
        for row in result.scalars().all():
            merged.setdefault(row.symbol, _snapshot_to_dict(row))
    except Exception as e:
        logger.warning("ETF snapshots unavailable: %s", e)

    # 4) Real NAV enrichment — override the price-proxy ``nav`` with the
    #    authoritative NAV from ``brsapi_nav_records`` (NAV صدور/ابطال) whenever a
    #    record exists. Also recompute ``nav_change``/``nav_change_pct`` from the
    #    two most recent NAV points so the change reflects the real NAV move.
    try:
        syms = list(merged.keys())
        if syms:
            rows = (
                await session.execute(
                    select(
                        NavRecordModel.symbol,
                        NavRecordModel.date,
                        NavRecordModel.nav_issue,
                        NavRecordModel.nav_redemption,
                    ).where(NavRecordModel.symbol.in_(syms))
                )
            ).all()
            per_sym: dict[str, list[tuple[str, float]]] = {}
            for sym, d, nav_issue, nav_redemption in rows:
                if not d:
                    continue
                nav = nav_issue or nav_redemption or 0
                if not nav:
                    continue
                per_sym.setdefault(sym, []).append((str(d), float(nav)))
            for sym, raw_points in per_sym.items():
                f = merged.get(sym)
                if f is None:
                    continue
                # Deduplicate by date (keep the last value per day) so intraday
                # NAV updates never make the day-over-day change look intraday.
                by_date: dict[str, float] = {}
                for d, nav in raw_points:
                    by_date[d] = nav
                points = sorted(by_date.items())
                latest_date, latest_nav = points[-1]
                f["nav"] = latest_nav
                f["nav_source"] = "nav_record"
                f["nav_date"] = latest_date
                if len(points) >= 2:
                    prev_date, prev_nav = points[-2]
                    if prev_nav:
                        f["nav_change"] = round(latest_nav - prev_nav, 2)
                        f["nav_change_pct"] = round((latest_nav - prev_nav) / prev_nav * 100, 2)
                        f["nav_prev_date"] = prev_date
            if per_sym:
                logger.info("Real NAV applied to %d funds from nav_records", len(per_sym))
    except Exception as e:
        logger.warning("NAV record enrichment unavailable: %s", e)

    return merged


async def _load_nav_history(session: AsyncSession, symbol: str) -> list[dict[str, Any]]:
    """NAV history for a fund.

    Sources (merged by date):
      - ``brsapi_nav_records``   → NAV صدور/ابطال برای ETFها
      - ``brsapi_ime_funds``     → اسنپ‌شات‌های روزانه قیمت صندوق‌های کالایی
    """
    by_date: dict[str, dict[str, Any]] = {}

    try:
        result = await session.execute(
            select(NavRecordModel).where(NavRecordModel.symbol == symbol).order_by(NavRecordModel.date.asc())
        )
        for r in result.scalars().all():
            d = r.date or ""
            if not d:
                continue
            nav = r.nav_issue or r.nav_redemption or 0
            if not nav:
                continue
            by_date[d] = {"date": d, "nav": float(nav), "source": "nav_record"}
    except Exception as e:
        logger.debug("NAV records unavailable for %s: %s", symbol, e)

    try:
        # IME fund daily snapshots → one price_close per day
        result = await session.execute(
            select(
                ImeFundModel.fetched_at,
                func.max(ImeFundModel.price_close),
            )
            .where(
                ImeFundModel.symbol == symbol,
                ImeFundModel.price_close.is_not(None),
                ImeFundModel.price_close > 0,
            )
            .group_by(ImeFundModel.fetched_at)
            .order_by(ImeFundModel.fetched_at.asc())
        )
        for fetched_at, nav in result.all():
            d = str(fetched_at)[:10] if fetched_at else ""
            if not d or not nav:
                continue
            if d not in by_date:
                by_date[d] = {"date": d, "nav": float(nav), "source": "ime_snapshot"}
    except Exception as e:
        logger.debug("IME fund NAV history unavailable for %s: %s", symbol, e)

    history = sorted(by_date.values(), key=lambda x: x["date"])
    # Cap at last 365 entries
    return history[-365:]


# ── Endpoints ──


@router.get("", summary="لیست همه صندوق‌ها")
async def list_funds(
    search: str | None = Query(None, description="جستجو در نام و نماد"),
    fund_type: str | None = Query(None, description="نوع صندوق (سهامی، درآمد ثابت، اهرمی، مختلط، بخشی، اختصاصی)"),
    market: str | None = Query(None, description="بازار (tse / ime)"),
    min_nav_change: float | None = Query(None, description="حداقل درصد تغییر NAV"),
    sort_by: str = Query(
        "nav", description="مرتب‌سازی: nav / nav_change_pct / trade_volume / market_value / symbol / name"
    ),
    sort_desc: bool = Query(True, description="نزولی؟"),
    limit: int = Query(200, ge=1, le=500, description="تعداد نتایج"),
    offset: int = Query(0, ge=0, description="شروع از"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """لیست واقعی صندوق‌های بورس تهران و بورس کالا با فیلتر و مرتب‌سازی."""
    funds = list((await _get_cached_funds(session)).values())

    # ── Filter ──
    if search:
        s = search.strip().lower()
        funds = [
            f
            for f in funds
            if s in f["symbol"].lower() or s in (f["name"] or "").lower() or s in (f["isin"] or "").lower()
        ]
    if fund_type:
        funds = [f for f in funds if f.get("fund_type") == fund_type]
    if market:
        funds = [f for f in funds if f.get("market") == market]
    if min_nav_change is not None:
        funds = [f for f in funds if (f.get("nav_change_pct") or 0) >= min_nav_change]

    # ── Sort ──
    sort_field_map = {
        "nav": "nav",
        "nav_change_pct": "nav_change_pct",
        "trade_volume": "trade_volume",
        "market_value": "market_value",
        "symbol": "symbol",
        "name": "name",
    }
    field = sort_field_map.get(sort_by, "nav")
    if field == "symbol":
        funds.sort(key=lambda f: f.get(field) or "", reverse=sort_desc)
    else:
        funds.sort(key=lambda f: f.get(field) or 0, reverse=sort_desc)

    total = len(funds)
    page_items = funds[offset : offset + limit]

    # ── Type / market breakdown ──
    type_counts: dict[str, int] = {}
    market_counts: dict[str, int] = {}
    for f in funds:
        ft = f.get("fund_type") or _infer_fund_type(f["name"], f["symbol"])
        type_counts[ft] = type_counts.get(ft, 0) + 1
        mk = f.get("market", "other")
        market_counts[mk] = market_counts.get(mk, 0) + 1

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": page_items,
        "type_counts": type_counts,
        "market_counts": market_counts,
    }


@router.get("/types", summary="لیست انواع صندوق‌ها")
async def list_fund_types() -> list[dict[str, str]]:
    """انواع صندوق‌های سرمایه‌گذاری با کلید انگلیسی و نام فارسی."""
    return [
        {"key": "سهامی", "label": "سهامی"},
        {"key": "درآمد ثابت", "label": "درآمد ثابت"},
        {"key": "اهرمی", "label": "اهرمی"},
        {"key": "مختلط", "label": "مختلط"},
        {"key": "بخشی", "label": "بخشی"},
        {"key": "اختصاصی", "label": "اختصاصی"},
    ]


@router.get("/top", summary="صندوق‌های برتر بر اساس معیارهای مختلف")
async def get_top_funds(
    metric: str = Query(
        "market_value",
        description="market_value / trade_volume / trade_value / nav_change_pct / intraday_volume",
    ),
    top: int = Query(20, ge=1, le=100, description="تعداد نتایج"),
    fund_type: str | None = Query(None, description="فیلتر نوع صندوق"),
    market: str | None = Query(None, description="فیلتر بازار (tse/ime)"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """رتبه‌بندی صندوق‌ها بر اساس metric.

    metric=market_value      → market_value اسنپ‌شات (اندازه صندوق)
    metric=trade_volume      → حجم معاملات روز (تعداد سهام)
    metric=trade_value       → ارزش معاملات روز (ریال)
    metric=nav_change_pct    → درصد تغییر NAV
    metric=intraday_volume   → حجم تیک‌های درون‌روز از brsapi_intraday_trades
    """
    funds = list((await _get_cached_funds(session)).values())

    # Optional filters (use same logic as /funds).
    if fund_type:
        funds = [f for f in funds if f.get("fund_type") == fund_type]
    if market:
        funds = [f for f in funds if f.get("market") == market]

    if metric == "intraday_volume":
        # Per-symbol latest trade_date (each fund may have its own latest day).
        from sqlalchemy import func
        from sqlalchemy import select as _select

        last_per_sym_rows = (
            await session.execute(
                _select(
                    IntradayTradeModel.symbol,
                    func.max(IntradayTradeModel.trade_date).label("ld"),
                )
                .where(IntradayTradeModel.symbol.in_([f["symbol"] for f in funds]))
                .group_by(IntradayTradeModel.symbol)
            )
        ).all()
        last_per_sym = {s: ld for s, ld in last_per_sym_rows if ld}

        # Aggregate tick counts per (symbol, last_date).
        if last_per_sym:
            # Build a values list: (symbol, date) pairs.
            pairs = list(last_per_sym.items())
            # Split: one query per (date, [symbols]) for efficiency.
            by_date: dict[str, list[str]] = {}
            for sym, ld in pairs:
                by_date.setdefault(str(ld), []).append(sym)
            tick_map: dict[str, int] = {}
            for ld, syms in by_date.items():
                rows = (
                    await session.execute(
                        _select(
                            IntradayTradeModel.symbol,
                            func.count(IntradayTradeModel.id),
                        )
                        .where(
                            IntradayTradeModel.trade_date == ld,
                            IntradayTradeModel.symbol.in_(syms),
                        )
                        .group_by(IntradayTradeModel.symbol)
                    )
                ).all()
                for sym, n in rows:
                    tick_map[sym] = int(n or 0)
        else:
            tick_map = {}
        for f in funds:
            f["_sort"] = tick_map.get(f["symbol"], 0)
    else:
        key_map = {
            "market_value": lambda f: float(f.get("market_value") or 0),
            "trade_volume": lambda f: float(f.get("trade_volume") or 0),
            "trade_value": lambda f: float(f.get("trade_value") or 0),
            "nav_change_pct": lambda f: float(f.get("nav_change_pct") or 0),
        }
        kf = key_map.get(metric)
        if kf is None:
            return {
                "metric": metric,
                "error": f"unknown metric; use one of: {list(key_map)} | intraday_volume",
                "items": [],
            }
        for f in funds:
            f["_sort"] = kf(f)

    funds.sort(key=lambda f: f["_sort"], reverse=True)
    items = [
        {
            "rank": i + 1,
            "symbol": f["symbol"],
            "name": f.get("name") or f["symbol"],
            "fund_type": f.get("fund_type"),
            "market": f.get("market"),
            "nav": f.get("nav"),
            "nav_change_pct": f.get("nav_change_pct"),
            "market_value": f.get("market_value"),
            "trade_volume": f.get("trade_volume"),
            "trade_value": f.get("trade_value"),
            "metric_value": f["_sort"],
        }
        for i, f in enumerate(funds[:top])
    ]
    return {
        "metric": metric,
        "total_considered": len(funds),
        "items": items,
    }


# ── Fund market overview (FundBase-style homepage) ──────────────────────────

_OVERVIEW_CACHE_TTL = 120.0
_overview_cache_lock = asyncio.Lock()
_overview_cache: dict[str, Any] | None = None
_overview_cache_at: float = 0.0

# Shamsi periods used for cash-flow / return comparisons
_CASHFLOW_PERIODS: dict[str, int] = {
    "today": 0,
    "1w": 7,
    "1m": 31,
    "3m": 92,
    "6m": 183,
    "1y": 365,
}
_RETURN_PERIODS: dict[str, int] = {
    key: _CASHFLOW_PERIODS[d] for key, d in (("m1", "1m"), ("m3", "3m"), ("m6", "6m"), ("y1", "1y"))
}


def _shamsi_days_ago(days: int) -> str:
    """Return a Shamsi date string (YYYY-MM-DD) ``days`` before today."""
    today = jdatetime.date.today()
    target = today - jdatetime.timedelta(days=days)
    return f"{target.year:04d}-{target.month:02d}-{target.day:02d}"


async def _latest_price_per_symbol(session: AsyncSession, symbols: list[str]) -> dict[str, float]:
    """Latest ``price_close`` per symbol from the historical daily table."""
    if not symbols:
        return {}
    out: dict[str, float] = {}
    try:
        stmt = text(
            "SELECT DISTINCT ON (symbol) symbol, price_close "
            "FROM brsapi_historical_daily "
            "WHERE symbol = ANY(:syms) AND price_close > 0 "
            "ORDER BY symbol, date DESC"
        )
        for sym, price in (await session.execute(stmt, {"syms": symbols})).all():
            if price:
                out[sym] = float(price)
    except Exception:
        logger.exception("Latest prices query failed")
    return out


async def _price_at_or_after(session: AsyncSession, symbols: list[str], boundary: str) -> dict[str, float]:
    """First available ``price_close`` per symbol with ``date >= boundary``."""
    if not symbols:
        return {}
    out: dict[str, float] = {}
    try:
        stmt = text(
            "SELECT DISTINCT ON (symbol) symbol, price_close "
            "FROM brsapi_historical_daily "
            "WHERE symbol = ANY(:syms) AND date >= :boundary AND price_close > 0 "
            "ORDER BY symbol, date ASC"
        )
        for sym, price in (await session.execute(stmt, {"syms": symbols, "boundary": boundary})).all():
            if price:
                out[sym] = float(price)
    except Exception:
        logger.exception("Period price query failed")
    return out


async def _net_real_inflow_per_symbol(session: AsyncSession, symbols: list[str], boundary: str) -> dict[str, float]:
    """Net real-person cash inflow (ریال) per symbol over ``date >= boundary``."""
    if not symbols:
        return {}
    out: dict[str, float] = {}
    try:
        stmt = text(
            "SELECT symbol, SUM(COALESCE(buy_real_value, 0) - COALESCE(sell_real_value, 0)) AS net "
            "FROM brsapi_historical_real_legal "
            "WHERE symbol = ANY(:syms) AND date >= :boundary "
            "GROUP BY symbol"
        )
        for sym, net in (await session.execute(stmt, {"syms": symbols, "boundary": boundary})).all():
            if net:
                out[sym] = float(net)
    except Exception:
        logger.exception("Real inflow query failed")
    return out


async def _build_fund_overview(session: AsyncSession) -> dict[str, Any]:
    """Compute the FundBase-style market overview from real data."""
    funds = list((await _get_cached_funds(session)).values())
    if not funds:
        return {}

    # Only funds that actually traded today (valid price) count as "tradeable".
    tradeable = [f for f in funds if (f.get("nav") or f.get("price_last") or 0) > 0]
    symbols = [f["symbol"] for f in tradeable]

    # Normalize legacy fund_type labels into the rich taxonomy so a fund never
    # lands in two buckets (e.g. "سهامی" vs "سهامی عادی").
    _TYPE_FIXES = {
        "سهامی": "سهامی عادی",
        "اختصاصی": "خصوصی",
        "صندوق سهامی": "سهامی عادی",
        "درامد ثابت": "درآمد ثابت",
    }

    def _norm_type(t: str) -> str:
        return _TYPE_FIXES.get(t, t)

    symbol_to_type = {
        f["symbol"]: _norm_type(f.get("fund_type") or _infer_fund_type(f.get("name"), f.get("symbol")))
        for f in tradeable
    }
    type_to_symbols: dict[str, list[str]] = {}
    for f in tradeable:
        type_to_symbols.setdefault(symbol_to_type[f["symbol"]], []).append(f["symbol"])

    # ── Today stats per fund ──
    today_change: dict[str, float] = {}
    today_value: dict[str, float] = {}
    today_inflow: dict[str, float] = {}
    for f in tradeable:
        sym = f["symbol"]
        today_change[sym] = float(f.get("nav_change_pct") or 0)
        today_value[sym] = float(f.get("trade_value") or 0)
        buy_v = float(f.get("buy_real_volume") or 0)
        sell_v = float(f.get("sell_real_volume") or 0)
        price = float(f.get("nav") or f.get("price_last") or 0)
        today_inflow[sym] = (buy_v - sell_v) * price

    # ── Category aggregation (today) ──
    def _trimmed_mean(values: list[float]) -> float:
        sane = [v for v in values if -30.0 <= v <= 30.0]
        if len(sane) >= max(3, len(values) // 2):
            return sum(sane) / len(sane)
        return sum(values) / len(values) if values else 0.0

    categories: list[dict[str, Any]] = []
    for ftype, syms in type_to_symbols.items():
        changes = [today_change[s] for s in syms]
        vals = [today_value[s] for s in syms]
        inflows = [today_inflow[s] for s in syms]
        categories.append(
            {
                "name": ftype,
                "count": len(syms),
                "avg_change_pct": round(_trimmed_mean(changes), 2),
                "trade_value": round(sum(vals), 0),
                "real_inflow": round(sum(inflows), 0),
            }
        )
    categories.sort(key=lambda c: -c["trade_value"])
    total_value = sum(c["trade_value"] for c in categories) or 1
    for c in categories:
        c["share_pct"] = round(c["trade_value"] / total_value * 100, 1)

    meaningful = [c for c in categories if c["count"] >= 3]
    top_category = max(meaningful or categories, key=lambda c: c["avg_change_pct"]) if categories else None

    # Robust average: trim extreme outliers (±30%) that come from bad snapshots,
    # then fall back to the plain mean if nothing survives the trim.
    changes_all = [today_change[s] for s in symbols]
    sane = [c for c in changes_all if -30.0 <= c <= 30.0]
    if len(sane) >= max(3, len(changes_all) // 2):
        avg_change = round(sum(sane) / len(sane), 2)
    else:
        avg_change = round(sum(changes_all) / len(changes_all), 2) if changes_all else 0.0

    # ── Top funds (top 10 each) ──
    _rank_keys: dict[str, Any] = {
        "growth": lambda f: float(f.get("nav_change_pct") or 0),
        "value": lambda f: float(f.get("trade_value") or 0),
        "inflow": lambda f: today_inflow.get(f["symbol"], 0.0),
    }

    def _ranked(key: str) -> list[dict[str, Any]]:
        ranked = sorted(tradeable, key=_rank_keys[key], reverse=True)[:10]
        return [
            {
                "symbol": f["symbol"],
                "name": f.get("name") or f["symbol"],
                "change_pct": round(float(f.get("nav_change_pct") or 0), 2),
                "trade_value": round(float(f.get("trade_value") or 0), 0),
                "real_inflow": round(today_inflow.get(f["symbol"], 0.0), 0),
            }
            for f in ranked
        ]

    top_funds = {
        "growth": _ranked("growth"),
        "value": _ranked("value"),
        "inflow": _ranked("inflow"),
    }

    # ── Trade value breakdown (donut) ──
    trade_breakdown = [{"name": c["name"], "value": c["trade_value"], "pct": c["share_pct"]} for c in categories]

    # ── Historical returns per category (m1/m3/m6/y1) ──
    # Returns are per-fund ``(latest / period_start - 1)`` and then aggregated per
    # category with a robust median (bad rows / unit changes are trimmed).
    def _robust_return(values: list[float]) -> float | None:
        sane = [v for v in values if abs(v) <= 400.0]  # drop impossible moves (>4x)
        if not sane:
            return None
        return round(statistics.median(sane), 2) if len(sane) >= 3 else round(sum(sane) / len(sane), 2)

    latest = await _latest_price_per_symbol(session, symbols)
    returns: list[dict[str, Any]] = []
    if latest:
        for ftype, syms in type_to_symbols.items():
            row: dict[str, Any] = {"name": ftype}
            for key, days in _RETURN_PERIODS.items():
                boundary = _shamsi_days_ago(days)
                start = await _price_at_or_after(session, syms, boundary)
                vals: list[float] = []
                for s in syms:
                    cur = latest.get(s)
                    st = start.get(s)
                    if cur and st and st > 0:
                        vals.append((cur / st - 1) * 100)
                row[key] = _robust_return(vals)
            if any(v is not None for v in row.values() if isinstance(v, (int, float))):
                returns.append(row)
        returns.sort(key=lambda r: -(r.get("y1") or 0))

    # ── Cash flow per category per period (میلیارد تومان) ──
    # The historical real/legal table may lag calendar today (weekends/holidays),
    # so "today" uses the latest available date in the table.
    cashflow: dict[str, dict[str, float]] = {}
    real_latest_date: str | None = None
    try:
        r = await session.execute(
            text("SELECT MAX(date) FROM brsapi_historical_real_legal WHERE symbol = ANY(:syms)"),
            {"syms": symbols},
        )
        real_latest_date = r.scalar_one_or_none()
    except Exception:
        logger.exception("Latest real/legal date query failed")

    for period, days in _CASHFLOW_PERIODS.items():
        boundary = _shamsi_days_ago(days)
        if period == "today" and real_latest_date and boundary > real_latest_date:
            boundary = real_latest_date
        inflow = await _net_real_inflow_per_symbol(session, symbols, boundary)
        per_type: dict[str, float] = {}
        for sym, net in inflow.items():
            t = symbol_to_type.get(sym)
            if not t:
                continue
            per_type[t] = per_type.get(t, 0.0) + net
        # Convert ریال → میلیارد تومان (1 میلیارد تومان = 1e9 تومان = 1e10 ریال)
        cashflow[period] = {t: round(v / 1e10, 2) for t, v in per_type.items()}

    return {
        "updated_at": utc_now_naive().isoformat(),
        "summary": {
            "fund_count": len(tradeable),
            "category_count": len(categories),
            "avg_change_pct": avg_change,
            "top_category": top_category,
            "total_trade_value": round(total_value, 0),
        },
        "categories": categories,
        "top_funds": top_funds,
        "trade_breakdown": trade_breakdown,
        "returns": returns,
        "cashflow": cashflow,
        "cashflow_periods": list(_CASHFLOW_PERIODS.keys()),
    }


async def _rebuild_overview_cache() -> None:
    """Background task: rebuild the overview cache with its own DB session."""
    try:
        from core.database import async_session_factory

        if async_session_factory is None:
            return
        async with async_session_factory() as session:
            data = await _build_fund_overview(session)
            async with _overview_cache_lock:
                global _overview_cache, _overview_cache_at
                _overview_cache = data
                _overview_cache_at = time.monotonic()
                logger.info("Fund overview refreshed in background: %d categories", len(data.get("categories", [])))
    except Exception:
        logger.exception("Background fund overview refresh failed")


@router.get("/overview", summary="نمای کلی بازار صندوق‌ها (سبک فاندبیس)")
async def fund_overview(
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict[str, Any]]:
    """داده‌های داشبورد صندوق‌های بورس تهران: خلاصه، دسته‌بندی‌ها، برترین‌ها، بازده دوره‌ای، جریان نقدینگی.

    Stale-while-revalidate: on expiry we trigger a background rebuild (own session)
    and serve the previous snapshot, so a cold-cache rebuild never blocks the
    homepage request.
    """
    global _overview_cache, _overview_cache_at
    now = time.monotonic()
    if _overview_cache is not None and (now - _overview_cache_at) < _OVERVIEW_CACHE_TTL:
        return ApiResponse(success=True, data=_overview_cache)
    if _overview_cache is not None and _overview_cache_lock.locked():
        return ApiResponse(success=True, data=_overview_cache)
    async with _overview_cache_lock:
        now = time.monotonic()
        if _overview_cache is not None and (now - _overview_cache_at) < _OVERVIEW_CACHE_TTL:
            return ApiResponse(success=True, data=_overview_cache)
        if _overview_cache is not None:
            _overview_cache_at = time.monotonic()  # avoid re-triggering on every request
            asyncio.create_task(_rebuild_overview_cache())
            return ApiResponse(success=True, data=_overview_cache)
        try:
            data = await _build_fund_overview(session)
            _overview_cache = data
            _overview_cache_at = time.monotonic()
            logger.info("Fund overview built (first time): %d categories", len(data.get("categories", [])))
            return ApiResponse(success=True, data=data)
        except Exception as exc:
            logger.exception("Fund overview failed")
            return ApiResponse(success=False, data={}, error={"message": safe_error_message(exc)})


@router.get("/nav-history", summary="تاریخچه NAV گروهی چند صندوق (برای اسپارکلاین‌ها)")
async def get_funds_nav_history(
    symbols: str = Query(..., description="نمادها با کاما جدا شده (حداکثر ۲۰۰)"),
    limit: int = Query(60, ge=5, le=365, description="حداکثر نقطه به‌ازای هر نماد"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """سری زمانی NAV برای چند نماد در یک درخواست.

    منبع اصلی: ``brsapi_nav_records`` (NAV صدور/ابطال). برای صندوق‌های کالایی
    که رکورد NAV ندارند، از اسنپ‌شات‌های روزانه ``brsapi_ime_funds`` استفاده
    می‌شود. خروجی: ``{"symbols": {نماد: [{date, nav, source}, ...]}}``
    """
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()][:200]
    result: dict[str, list[dict[str, Any]]] = {}
    if not sym_list:
        return {"symbols": result}

    try:
        rows = (
            await session.execute(
                select(
                    NavRecordModel.symbol,
                    NavRecordModel.date,
                    NavRecordModel.nav_issue,
                    NavRecordModel.nav_redemption,
                )
                .where(NavRecordModel.symbol.in_(sym_list))
                .order_by(NavRecordModel.symbol, NavRecordModel.date.asc())
            )
        ).all()
        per_sym: dict[str, list[dict[str, Any]]] = {}
        for sym, d, nav_issue, nav_redemption in rows:
            if not d:
                continue
            nav = nav_issue or nav_redemption or 0
            if not nav:
                continue
            per_sym.setdefault(sym, []).append({"date": str(d), "nav": float(nav), "source": "nav_record"})
    except Exception as e:
        logger.debug("Bulk NAV records unavailable: %s", e)

    # IME commodity-fund fallback: one price_close per fetched day.
    try:
        ime_rows = (
            await session.execute(
                select(
                    ImeFundModel.symbol,
                    ImeFundModel.fetched_at,
                    func.max(ImeFundModel.price_close),
                )
                .where(
                    ImeFundModel.symbol.in_(sym_list),
                    ImeFundModel.price_close.is_not(None),
                    ImeFundModel.price_close > 0,
                )
                .group_by(ImeFundModel.symbol, ImeFundModel.fetched_at)
            )
        ).all()
        for sym, fetched_at, nav in ime_rows:
            d = str(fetched_at)[:10] if fetched_at else ""
            if not d or not nav:
                continue
            series = per_sym.setdefault(sym, [])
            if all(p["date"] != d for p in series):
                series.append({"date": d, "nav": float(nav), "source": "ime_snapshot"})
    except Exception as e:
        logger.debug("IME NAV history unavailable: %s", e)

    for sym, series in per_sym.items():
        # Deduplicate by date (keep one value per day) so intraday NAV updates
        # never produce a jumpy/flat sparkline. When both a nav_record and an
        # IME snapshot share a date, the authoritative nav_record wins.
        by_date: dict[str, dict[str, Any]] = {}
        for p in series:
            cur = by_date.get(p["date"])
            if cur is None or (p.get("source") == "nav_record" and cur.get("source") != "nav_record"):
                by_date[p["date"]] = p
        ordered = sorted(by_date.values(), key=lambda p: p["date"])
        result[sym] = ordered[-limit:]
    return {"symbols": result}


@router.get("/intraday", summary="تیک‌های درون‌روز چند صندوق (از brsapi_intraday_trades)")
async def get_funds_intraday(
    symbols: str = Query(..., description="نمادها با کاما جدا (حداکثر ۲۰)"),
    date: str | None = Query(None, description="تاریخ شمسی YYYY-MM-DD؛ پیش‌فرض آخرین روز موجود برای هر نماد"),
    limit: int = Query(5000, ge=1, le=50000, description="حداکثر تیک به‌ازای هر نماد"),
    include_canceled: bool = Query(False, description="شامل تیک‌های کنسل‌شده؟"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """ریز معاملات (تیک) صندوق‌ها از جدول ``brsapi_intraday_trades``.

    - اگر ``date`` خالی باشد، برای هر نماد آخرین روز موجود انتخاب می‌شود
      (هر صندوق ممکن است تاریخ متفاوتی داشته باشد).
    - پاسخ برای هر نماد شامل خلاصه + آرایه تیک‌ها به ترتیب زمانی است.
    """
    from sqlalchemy import or_, select

    sym_list = [s.strip() for s in symbols.split(",") if s.strip()][:20]
    if not sym_list:
        return {"symbols": {}}

    result: dict[str, dict[str, Any]] = {}
    # 1) Resolve per-symbol target date (unless caller forced one).
    per_sym_date: dict[str, str] = {}
    if date:
        per_sym_date = dict.fromkeys(sym_list, date)
    else:
        try:
            last_q = (
                await session.execute(
                    select(
                        IntradayTradeModel.symbol,
                        IntradayTradeModel.trade_date,
                    )
                    .where(IntradayTradeModel.symbol.in_(sym_list))
                    .order_by(IntradayTradeModel.symbol, IntradayTradeModel.trade_date.desc())
                )
            ).all()
            for sym, d in last_q:
                if d and sym not in per_sym_date:
                    per_sym_date[sym] = str(d)
        except Exception:
            logger.exception("intraday last-date query failed")

    # 2) Pull ticks for each (symbol, date).
    for sym in sym_list:
        d = per_sym_date.get(sym)
        if not d:
            result[sym] = {"trade_date": None, "ticks": [], "summary": None}
            continue
        try:
            stmt = (
                select(IntradayTradeModel)
                .where(
                    IntradayTradeModel.symbol == sym,
                    IntradayTradeModel.trade_date == d,
                )
                .order_by(IntradayTradeModel.time.asc())
                .limit(limit)
            )
            if not include_canceled:
                stmt = stmt.where(
                    or_(
                        IntradayTradeModel.canceled.is_(False),
                        IntradayTradeModel.canceled.is_(None),
                    )
                )
            rows = (await session.execute(stmt)).scalars().all()
            ticks = [
                {
                    "time": r.time,
                    "price": float(r.price) if r.price is not None else None,
                    "volume": int(r.volume) if r.volume is not None else 0,
                    "canceled": bool(r.canceled) if r.canceled is not None else False,
                }
                for r in rows
            ]
            prices = [t["price"] for t in ticks if t["price"]]
            vols = [t["volume"] for t in ticks]
            summary = None
            if prices:
                summary = {
                    "count": len(ticks),
                    "first_price": prices[0],
                    "last_price": prices[-1],
                    "price_min": min(prices),
                    "price_max": max(prices),
                    "volume": sum(vols),
                    "value": sum(p * v for p, v in zip(prices, vols, strict=False)),
                    "first_time": ticks[0]["time"],
                    "last_time": ticks[-1]["time"],
                }
            result[sym] = {"trade_date": d, "ticks": ticks, "summary": summary}
        except Exception as e:
            logger.exception("intraday fetch failed for %s", sym)
            result[sym] = {"trade_date": d, "ticks": [], "error": str(e)[:120]}

    return {"symbols": result}


@router.get("/intraday/candles", summary="کندل OHLCV دقیقه‌ای برای یک یا چند صندوق")
async def get_funds_intraday_candles(
    symbols: str = Query(..., description="نمادها با کاما جدا (حداکثر ۱۰)"),
    date: str | None = Query(None, description="تاریخ شمسی YYYY-MM-DD (پیش‌فرض: آخرین روز)"),
    interval_minutes: int = Query(1, ge=1, le=60, description="بازه کندل به دقیقه"),
    include_canceled: bool = Query(False, description="شامل تیک‌های کنسل‌شده؟"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """کندل ۱ (یا N) دقیقه‌ای از تیک‌های درون‌روز.

    Aggregation در دیتابیس انجام می‌شود (GROUP BY minute bucket) — برای
    صندوق‌های پرمعامله مثل عیار با ۶۰۰K+ تیک سریع است.
    """
    from sqlalchemy import func, or_

    sym_list = [s.strip() for s in symbols.split(",") if s.strip()][:10]
    if not sym_list:
        return {"symbols": {}}

    bucket_expr = func.substr(IntradayTradeModel.time, 1, 5)  # HH:MM

    result: dict[str, dict[str, Any]] = {}
    for sym in sym_list:
        try:
            # Resolve date.
            target = date
            if not target:
                target = str(
                    (
                        await session.execute(
                            select(IntradayTradeModel.trade_date)
                            .where(IntradayTradeModel.symbol == sym)
                            .order_by(IntradayTradeModel.trade_date.desc())
                            .limit(1)
                        )
                    ).scalar()
                    or ""
                )
            if not target:
                result[sym] = {"trade_date": None, "candles": []}
                continue

            base = (
                select(
                    bucket_expr.label("m"),
                    func.min(IntradayTradeModel.price).label("lo"),
                    func.max(IntradayTradeModel.price).label("hi"),
                    func.sum(IntradayTradeModel.volume).label("vol"),
                    func.sum(IntradayTradeModel.price * IntradayTradeModel.volume).label("val"),
                    func.count(IntradayTradeModel.id).label("n"),
                )
                .where(
                    IntradayTradeModel.symbol == sym,
                    IntradayTradeModel.trade_date == target,
                    IntradayTradeModel.price.is_not(None),
                    IntradayTradeModel.price > 0,
                )
                .group_by(bucket_expr)
                .order_by(bucket_expr)
            )
            if not include_canceled:
                base = base.where(
                    or_(
                        IntradayTradeModel.canceled.is_(False),
                        IntradayTradeModel.canceled.is_(None),
                    )
                )

            # First/last per bucket — needs a subquery because of GROUP BY.
            # Use array_agg trick: take min and max row id per bucket, then join.
            rows = (await session.execute(base)).all()
            if not rows:
                result[sym] = {"trade_date": target, "candles": []}
                continue

            # For first/last price per minute, fetch the bucket with the
            # earliest/latest time row. Cheaper: just one extra query that
            # picks the first and last time per minute.
            min_max_subq = (
                select(
                    bucket_expr.label("m"),
                    func.min(IntradayTradeModel.time).label("first_time"),
                    func.max(IntradayTradeModel.time).label("last_time"),
                )
                .where(
                    IntradayTradeModel.symbol == sym,
                    IntradayTradeModel.trade_date == target,
                    IntradayTradeModel.price.is_not(None),
                    IntradayTradeModel.price > 0,
                )
                .group_by(bucket_expr)
                .subquery()
            )
            first_pick = select(
                min_max_subq.c.m,
                IntradayTradeModel.price.label("p"),
            ).join(
                IntradayTradeModel,
                (IntradayTradeModel.time == min_max_subq.c.first_time)
                & (IntradayTradeModel.symbol == sym)
                & (IntradayTradeModel.trade_date == target),
            )
            last_pick = select(
                min_max_subq.c.m,
                IntradayTradeModel.price.label("p"),
            ).join(
                IntradayTradeModel,
                (IntradayTradeModel.time == min_max_subq.c.last_time)
                & (IntradayTradeModel.symbol == sym)
                & (IntradayTradeModel.trade_date == target),
            )
            first_map: dict[str, float] = {r[0]: float(r[1]) for r in (await session.execute(first_pick)).all()}
            last_map: dict[str, float] = {r[0]: float(r[1]) for r in (await session.execute(last_pick)).all()}

            candles = []
            for m, lo, hi, vol, val, n in rows:
                vwap = float(val) / float(vol) if vol else 0.0
                candles.append(
                    {
                        "minute": m,
                        "open": first_map.get(m, float(lo)),
                        "high": float(hi),
                        "low": float(lo),
                        "close": last_map.get(m, float(lo)),
                        "volume": int(vol or 0),
                        "value": float(val or 0),
                        "vwap": round(vwap, 2),
                        "trades": int(n or 0),
                    }
                )

            # Optional: merge buckets into N-minute candles.
            if interval_minutes > 1:
                merged: list[dict[str, Any]] = []
                for i in range(0, len(candles), interval_minutes):
                    grp = candles[i : i + interval_minutes]
                    if not grp:
                        continue
                    merged.append(
                        {
                            "minute": grp[0]["minute"],
                            "open": grp[0]["open"],
                            "high": max(c["high"] for c in grp),
                            "low": min(c["low"] for c in grp),
                            "close": grp[-1]["close"],
                            "volume": sum(c["volume"] for c in grp),
                            "value": sum(c["value"] for c in grp),
                            "vwap": round(
                                sum(c["value"] for c in grp) / max(1, sum(c["volume"] for c in grp)),
                                2,
                            ),
                            "trades": sum(c["trades"] for c in grp),
                        }
                    )
                candles = merged

            result[sym] = {"trade_date": target, "candles": candles}
        except Exception as e:
            logger.exception("candles fetch failed for %s", sym)
            result[sym] = {"trade_date": date, "candles": [], "error": str(e)[:120]}

    return {"symbols": result}


@router.get("/intraday/stream", summary="Sreal-time ticks via Server-Sent Events")
async def stream_fund_intraday(
    symbols: str = Query(..., description="نمادها با کاما جدا (حداکثر ۵)"),
    poll_seconds: float = Query(5.0, ge=1.0, le=60.0, description="فاصله polling"),
    max_events: int = Query(500, ge=1, le=5000, description="حداکثر تعداد event قبل از قطع"),
    session: AsyncSession = Depends(get_db_session),
):
    """پخش زنده تیک‌های درون‌روز از طریق Server-Sent Events.

    هر ``poll_seconds`` ثانیه، تیک‌های جدید صندوق‌های انتخابی (نسبت به آخرین
    تیکی که client دریافت کرده) push می‌شوند. اگر تیک جدیدی نباشد heartbeat
    می‌فرستیم تا connection قطع نشود.
    """
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    sym_list = [s.strip() for s in symbols.split(",") if s.strip()][:5]
    if not sym_list:
        return {"error": "no symbols"}

    # Seed last_ids with the current max per symbol so we only stream
    # FUTURE ticks (no replay of history).
    last_ids: dict[str, int] = dict.fromkeys(sym_list, 0)
    try:
        from sqlalchemy import func as _func

        seed_rows = (
            await session.execute(
                select(
                    IntradayTradeModel.symbol,
                    _func.max(IntradayTradeModel.id),
                )
                .where(IntradayTradeModel.symbol.in_(sym_list))
                .group_by(IntradayTradeModel.symbol)
            )
        ).all()
        for sym, max_id in seed_rows:
            if max_id is not None:
                last_ids[sym] = int(max_id)
    except Exception:
        logger.exception("SSE seed query failed")

    async def _fetch_new() -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        try:
            for sym in sym_list:
                stmt = (
                    select(IntradayTradeModel)
                    .where(
                        IntradayTradeModel.symbol == sym,
                        IntradayTradeModel.id > last_ids[sym],
                    )
                    .order_by(IntradayTradeModel.id.asc())
                    .limit(500)
                )
                rows = (await session.execute(stmt)).scalars().all()
                for r in rows:
                    last_ids[sym] = max(last_ids[sym], r.id or 0)
                    events.append(
                        {
                            "symbol": sym,
                            "trade_date": r.trade_date,
                            "time": r.time,
                            "price": float(r.price) if r.price is not None else None,
                            "volume": int(r.volume) if r.volume is not None else 0,
                            "canceled": bool(r.canceled) if r.canceled is not None else False,
                        }
                    )
        except Exception:
            logger.exception("SSE fetch failed")
        return events

    async def event_gen():
        # Initial fetch to seed last_ids (so we don't replay history).
        with contextlib.suppress(Exception):
            await _fetch_new()
        sent = 0
        while sent < max_events:
            try:
                new_events = await _fetch_new()
                if new_events:
                    payload = json.dumps(
                        {"type": "ticks", "events": new_events},
                        ensure_ascii=False,
                    )
                    yield f"data: {payload}\n\n"
                    sent += len(new_events)
                else:
                    # Heartbeat
                    yield 'data: {"type": "heartbeat"}\n\n'
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("SSE stream iteration failed")
                yield 'data: {"type": "error"}\n\n'
                break
            await asyncio.sleep(poll_seconds)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{symbol}/nav", summary="تاریخچه NAV یک صندوق")
async def get_fund_nav(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """تاریخچه NAV صندوق (صدور/ابطال + اسنپ‌شات‌های روزانه)."""
    history = await _load_nav_history(session, symbol)
    return {
        "symbol": symbol,
        "history": history,
        "points": len(history),
        "latest": history[-1] if history else None,
        "oldest": history[0] if history else None,
    }


@router.get("/{symbol}", summary="جزئیات یک صندوق")
async def get_fund(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """اطلاعات کامل یک صندوق از داده‌های واقعی دیتابیس."""
    funds = await _get_cached_funds(session)
    fund = funds.get(symbol)
    if not fund:
        # try case-insensitive
        low = symbol.lower()
        for sym, f in funds.items():
            if sym.lower() == low:
                fund = f
                break
    if not fund:
        return {"symbol": symbol, "error": f"صندوق با نماد {symbol} یافت نشد", "found": False}

    # Shallow-copy so request-scoped fields never mutate the shared cache.
    fund = dict(fund)
    nav_history = await _load_nav_history(session, fund["symbol"])
    fund["nav_history"] = nav_history
    fund["nav_history_points"] = len(nav_history)
    fund["analysis"] = _compute_full_analysis(fund)
    fund["found"] = True
    return fund


@router.post("/sync-all", summary="همگام‌سازی انبوه صندوق‌ها از اسنپ‌شات‌های BrsApi")
async def sync_all_funds(
    limit: int = Query(20, ge=1, le=80, description="حداکثر تعداد صندوق برای همگام‌سازی"),
    session: AsyncSession = Depends(get_db_session),
    brsapi: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> dict[str, Any]:
    """پر کردن جدول ``funds`` از اسنپ‌شات‌های موجود (نیازی به API زنده ندارد).

    هر صندوق از ``get_enriched_symbol_detail`` (جدول brsapi_symbol_snapshots)
    خوانده و در جدول ``funds`` ذخیره می‌شود.
    """
    from services.fund_sync_service import KNOWN_FUND_SYMBOLS, FundSyncService

    symbols = KNOWN_FUND_SYMBOLS[:limit]
    sync = FundSyncService(
        fund_service=FundService(session=session),
        brsapi=brsapi,
    )
    report = await sync.sync_all_funds(symbols=symbols)
    await _invalidate_fund_cache()
    global _overview_cache, _overview_cache_at
    _overview_cache = None
    _overview_cache_at = 0.0
    return {
        "success": report.failed == 0 and report.success > 0,
        "total": report.total,
        "success_count": report.success,
        "failed_count": report.failed,
        "errors": report.errors[:20],
        "duration_ms": report.duration_ms,
        "message": report.summary,
    }


@router.post("/{symbol}/update", summary="به‌روزرسانی داده‌های یک صندوق از اسنپ‌شات‌های BrsApi")
async def update_fund_from_brsapi(
    symbol: str,
    fund_service: FundService = Depends(get_fund_service),
    brsapi: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> dict[str, Any]:
    """دریافت داده‌های لحظه‌ای یک صندوق از اسنپ‌شات‌های BrsApi و ذخیره در جدول ``funds``."""
    result = await fund_service.update_from_brsapi(symbol=symbol, brsapi=brsapi)
    await _invalidate_fund_cache()
    global _overview_cache, _overview_cache_at
    _overview_cache = None
    _overview_cache_at = 0.0
    return result


@router.get("/{symbol}/analysis", summary="تحلیل هوشمند یک صندوق (۶ بعد)")
async def get_fund_analysis(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """تحلیل کامل یک صندوق بر اساس ۶ بعد: مالی، نقدشوندگی، مدیریت، ریسک، هزینه، شفافیت."""
    funds = await _get_cached_funds(session)
    fund = funds.get(symbol)
    if not fund:
        return {"symbol": symbol, "error": f"صندوق با نماد {symbol} یافت نشد", "found": False}
    return _compute_full_analysis(dict(fund))


# ── Internal helpers (۶بعدی) ────────────────────────────────────────────────


def _compute_full_analysis(f: dict[str, Any]) -> dict[str, Any]:
    """تحلیل ۶‌بعدی روی داده واقعی (ساختار خروجی هماهنگ با موتور فرانت)."""
    nav_change = f.get("nav_change_pct") or 0
    trade_volume = f.get("trade_volume") or 0
    trade_value = f.get("trade_value") or 0
    trade_count = f.get("trade_count") or 0
    shares_count = f.get("shares_count") or 0
    market_value = f.get("market_value") or 0
    price_last = f.get("price_last") or 0
    price_max = f.get("price_max") or 0
    price_min = f.get("price_min") or 0
    price_yesterday = f.get("price_yesterday") or 0
    nav = f.get("nav") or 0
    isin = f.get("isin") or ""
    name = f.get("name") or ""
    buy_real = f.get("buy_real_volume") or 0
    buy_legal = f.get("buy_legal_volume") or 0
    sell_legal = f.get("sell_legal_volume") or 0

    # ── مالی ──
    financial = 60
    if nav_change > 1:
        financial += 20
    elif nav_change > 0.5:
        financial += 10
    elif nav_change > 0:
        financial += 5
    elif nav_change < -0.5:
        financial -= 15
    if nav > 10000:
        financial += 5
    if trade_count > 100:
        financial += 5
    financial = max(0, min(100, financial))

    # ── نقدشوندگی ──
    liquidity = 50
    if trade_volume > 1_000_000:
        liquidity += 30
    elif trade_volume > 500_000:
        liquidity += 20
    elif trade_volume > 100_000:
        liquidity += 10
    else:
        liquidity -= 15
    if trade_value > 1_000_000_000:
        liquidity += 10
    elif trade_value > 100_000_000:
        liquidity += 5
    else:
        liquidity -= 5
    if trade_count > 500:
        liquidity += 10
    elif trade_count > 100:
        liquidity += 5
    elif trade_count < 10:
        liquidity -= 10
    liquidity = max(0, min(100, liquidity))

    # ── مدیریت ──
    management = 65
    if shares_count > 50_000_000:
        management += 20
    elif shares_count > 10_000_000:
        management += 10
    elif shares_count < 1_000_000:
        management -= 15
    if market_value > 1_000_000_000_000:
        management += 10
    elif market_value > 100_000_000_000:
        management += 5
    else:
        management -= 5
    if (buy_legal - sell_legal) > 0:
        management += 5
    management = max(0, min(100, management))

    # ── ریسک ──
    risk = 60
    avg_price = (price_max + price_min) / 2
    if avg_price > 0:
        range_pct = (price_max - price_min) / avg_price
        if range_pct < 0.01:
            risk += 15
        elif range_pct < 0.03:
            risk += 10
        elif range_pct < 0.05:
            risk += 5
        elif range_pct > 0.10:
            risk -= 10
    if nav_change < -2:
        risk -= 15
    elif nav_change < -1:
        risk -= 10
    elif nav_change < -0.5:
        risk -= 5
    if trade_volume > 500_000:
        risk += 5
    risk = max(0, min(100, risk))

    # ── هزینه ──
    cost = 70
    if price_last > 0 and nav > 0:
        premium = ((price_last - nav) / nav) * 100
        if premium > 5:
            cost -= 15
        elif premium > 2:
            cost -= 5
        elif premium > 0:
            cost -= 2
    if trade_count > 1000:
        cost -= 5
    elif trade_count < 10:
        cost += 5
    cost = max(0, min(100, cost))

    # ── شفافیت ──
    transparency = 65
    if len(isin) > 5:
        transparency += 15
    if price_yesterday > 0:
        transparency += 5
    if price_max > 0 and price_min > 0:
        transparency += 5
    if len(name) > 3:
        transparency += 5
    if buy_real > 0 or buy_legal > 0:
        transparency += 5
    transparency = max(0, min(100, transparency))

    total = round(
        financial * 0.25 + liquidity * 0.20 + management * 0.18 + risk * 0.15 + cost * 0.12 + transparency * 0.10
    )

    issues_count = 0
    for check in (
        nav_change < -2,
        trade_volume < 100_000,
        market_value < 50_000_000_000,
        financial < 50,
        liquidity < 40,
    ):
        if check:
            issues_count += 1

    if total >= 80 and risk >= 50:
        rec = "STRONG_BUY"
    elif total >= 70:
        rec = "BUY"
    elif total >= 60:
        rec = "WATCHLIST"
    elif total >= 50:
        rec = "HOLD"
    elif total >= 40:
        rec = "REDUCE"
    else:
        rec = "AVOID"

    if total < 35 or issues_count >= 3:
        risk_level = "CRITICAL"
    elif total < 55 or issues_count >= 2:
        risk_level = "HIGH"
    elif total < 70 or issues_count >= 1:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    status = "عالی" if total >= 75 else "قابل قبول" if total >= 60 else "نیازمند بهبود" if total >= 40 else "ضعیف"

    return {
        "symbol": f["symbol"],
        "name": name,
        "scores": {
            "financial": financial,
            "liquidity": liquidity,
            "management": management,
            "risk": risk,
            "cost": cost,
            "transparency": transparency,
            "total": total,
        },
        "recommendation": rec,
        "risk_level": risk_level,
        "issues_count": issues_count,
        "summary": f"امتیاز کلی: {total}% - وضعیت: {status} - {issues_count} مشکل شناسایی شده",
    }
