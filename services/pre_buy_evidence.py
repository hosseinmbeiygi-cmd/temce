"""🔎 Evidence resolver for the pre-buy decision sheet.

Binds a symbol's live data to the evidence handles declared in
:mod:`core.question_bank.bank`. Deliberately **explicit**: every key maps to exactly one
named field of one named source. This is the lesson learned from
``fund-checklist-real.lookupEvidence``, which joins static rows to live data by fuzzy
keyword matching over prose and therefore reports confident-looking proxies for things it
cannot see (its own code says ``"معادل‌سازی ساختار بازار به جای شبکه"``). For a ★ stopper
that kind of substitution is worse than no data at all, so:

* a missing figure is returned as ``status="missing"`` with a Persian reason;
* keys the platform genuinely cannot answer (holder type is not stored anywhere) are
  listed as permanently unavailable, with the reason shown to the user;
* one failing source degrades to missing instead of failing the whole sheet.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.codal import CodalAnnouncementModel
from brsapi.models.ime import ImeFutureModel
from brsapi.models.tsetmc import NavRecordModel, SymbolDetailModel
from core.logging import get_logger
from core.question_bank.bank import evidence_by_key
from core.question_bank.schema import EvidenceValue
from models.codal import CodalAuditSummaryModel
from models.fund import FundModel
from models.market_data import CommodityOptionModel, StockOptionModel
from models.option import CorporateActionModel
from models.queue_analysis import QueueAnalysisResult
from models.stock_enterprise import StockQuantSignalModel

logger = get_logger(__name__)

#: Evidence the platform cannot produce today. Shown verbatim so the user knows the gap
#: is the app's, not their analysis — and the engine counts it as weak evidence.
#:
#: Everything below ``holders.`` is equity-era; the rest belongs to the instrument modules
#: in :mod:`core.question_bank.modules`. A module handle is allowed to live here only when no
#: column anywhere holds it: ``test_pre_buy_registry`` requires every declared handle of every
#: resolved bank to be either bound below `_RESOLVERS` or listed here with a reason.
PERMANENTLY_UNAVAILABLE: dict[str, str] = {
    "holders.institutional_pct": "نوع سهامدار (حقیقی/حقوقی) در brsapi_shareholder_records ذخیره نمی‌شود.",
    # صندوق (کلاس B) و اهرمی (H)
    "fund.fee": "کارمزد هیچ صندوقی در جداول برنامه ذخیره نمی‌شود.",
    "fund.manager": "نام مدیر و سابقهٔ او در جداول برنامه نیست.",
    "fund.track_error": "خطای ردیابی محاسبه نمی‌شود؛ شاخص مقایسهٔ صندوق ذخیره نیست.",
    "fund.redemption": "شرایط، هزینه و سقف ابطال/ایجاد واحد ذخیره نمی‌شود.",
    "fund.dissolution": "شرایط انحلال صندوق در جداول برنامه نیست.",
    "fund.portfolio": "ترکیب پرتفوی صندوق ذخیره نمی‌شود؛ فقط NAV روزانه هست.",
    "fund.dividend": "سابقهٔ تقسیم سود صندوق در جداول برنامه نیست.",
    "leveraged.ratio": "ضریب اهرم صندوق به‌صورت داده ذخیره نمی‌شود.",
    "leveraged.rebalance": "سازوکار بازسازی روزانه در جداول برنامه نیست.",
    # طلا و گواهی سکه (C)
    "gold.backing": "پشتوانهٔ هر واحد صندوق طلا در جداول برنامه نیست.",
    "gold.premium_history": "سابقهٔ پریمیوم ذخیره نمی‌شود؛ فقط NAV و قیمت امروز هست.",
    "gold.convergence": "سرعت همگرایی به قیمت واقعی سکه محاسبه نمی‌شود.",
    "gold.delivery": "شرایط برداشت فیزیکی گواهی در جداول برنامه نیست.",
    # بورس کالا (E)
    "commodity.mechanism": "نوع سازوکار (تحवیل/پشتوانه/تعهد) برای هر نماد ذخیره نمی‌شود.",
    "commodity.counterparty": "طرف تعهد و اعتبار او در جداول برنامه نیست.",
    "commodity.warehouse": "انبار، تأییدیهٔ کیفیت و هزینهٔ انبارداری ذخیره نمی‌شود.",
    "commodity.spot_gap": "قیمت نقدی کالا در کنار قیمت گواهی ذخیره نمی‌شود تا فاصله سنجیده شود.",
    "commodity.shock_history": "سابقهٔ رویداد-محور (شوک‌های قبلی کالا) ذخیره نیست.",
    # اختیار (F)
    "option.iv": "نوسان ضمنی محاسبه نمی‌شود؛ توالی قیمت لحظه‌ای قرارداد ذخیره نیست.",
    "option.spread": "قیمت‌های دو سمت سفارش‌نامهٔ قرارداد ذخیره نمی‌شود.",
    # آتی (G)
    "future.basis": "قیمت نقدی دارایی پایه در کنار قرارداد آتی ذخیره نمی‌شود.",
    "future.rollover": "هزینهٔ رول‌اور بین قراردادها ذخیره نمی‌شود.",
    "future.settlement_history": "سابقهٔ تسویهٔ روزانهٔ موقعیت ذخیره نمی‌شود.",
    "future.gap_history": "پیشینهٔ گپ‌های شدید قیمتی قرارداد به‌صورت دادهٔ جدا نیست.",
    # اوراق (A) — هیچ جدول اوراقی وجود ندارد
    "bond.publisher": "جدولی برای اوراق بدهی (اخزا/صکوک/گواهی سپرده بانکی) در برنامه نیست.",
    "bond.coupon": "نرخ سود اسمی و دورهٔ پرداخت اوراق ذخیره نمی‌شود.",
    "bond.maturity": "سررسید اوراق ذخیره نمی‌شود.",
    "bond.rating": "رتبهٔ اعتباری ناشر ذخیره نمی‌شود.",
    "bond.collateral": "وثیقه و پشتوانهٔ اوراق ذخیره نمی‌شود.",
    # عمومی
    "tax.rate": "نرخ مالیات هر ابزار به‌صورت دادهٔ بازار ذخیره نمی‌شود.",
}


@dataclass
class _Sources:
    """Everything the resolvers may read, fetched once per symbol."""

    detail: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None
    holders: list[dict[str, Any]] = field(default_factory=list)
    announcements: list[dict[str, Any]] = field(default_factory=list)
    report_count: int | None = None
    last_dividend: Any = None
    queue: dict[str, Any] | None = None
    signal: dict[str, Any] | None = None
    #: Non-equity sources: the fund row, its NAV history, and the contract tables.
    fund: dict[str, Any] | None = None
    nav: dict[str, Any] | None = None
    nav_history: list[dict[str, Any]] = field(default_factory=list)
    option: dict[str, Any] | None = None
    future: dict[str, Any] | None = None
    errors: dict[str, str] = field(default_factory=dict)

    def first_announcement_with(self, field_name: str) -> Any:
        for row in self.announcements:
            value = row.get(field_name)
            if value not in (None, "", 0):
                return value
        return None


def _d(src: _Sources, key: str) -> Any:
    """Snapshot/detail field, preferring the live-enriched snapshot."""

    if src.detail is not None:
        value = src.detail.get(key)
        if value not in (None, "", 0):
            return value
    if src.raw is not None:
        return src.raw.get(key)
    return None


def _audit(src: _Sources, key: str) -> Any:
    return src.audit.get(key) if src.audit else None


_RESOLVERS: dict[str, Callable[[_Sources], Any]] = {
    "detail.name": lambda s: _d(s, "name"),
    "detail.state": lambda s: _d(s, "state"),
    "detail.board": lambda s: _d(s, "board") or _d(s, "market"),
    "detail.sector": lambda s: _d(s, "sector") or _d(s, "sub_sector"),
    "detail.price_last": lambda s: _d(s, "price_last") or _d(s, "price_close"),
    "detail.price_yesterday": lambda s: _d(s, "price_yesterday"),
    "detail.price_min_year": lambda s: _d(s, "price_min_year"),
    "detail.price_max_year": lambda s: _d(s, "price_max_year"),
    "detail.tmin": lambda s: _d(s, "price_lowest_allowed"),
    "detail.tmax": lambda s: _d(s, "price_highest_allowed"),
    "detail.base_volume": lambda s: _d(s, "base_volume"),
    "detail.trade_value": lambda s: _d(s, "trade_value"),
    "detail.avg_volume_month": lambda s: _d(s, "trade_volume_avg_month"),
    "detail.shares_count": lambda s: _d(s, "shares_count") or _d(s, "shares_issued"),
    "detail.free_float": lambda s: _d(s, "free_float_pct"),
    "detail.eps": lambda s: _audit(s, "eps") or _d(s, "eps"),
    "detail.pe": lambda s: _d(s, "pe_ratio"),
    "detail.group_pe": lambda s: _d(s, "group_pe_ratio"),
    "detail.ps": lambda s: _d(s, "ps_ratio"),
    "detail.market_cap": lambda s: _d(s, "market_value"),
    "codal.last_report": lambda s: s.first_announcement_with("date_publish")
    or (s.audit or {}).get("report_date"),
    "codal.report_count": lambda s: s.report_count,
    "codal.audit_status": lambda s: s.first_announcement_with("audit_status"),
    "fin.revenue_growth": lambda s: _audit(s, "revenue_growth"),
    "fin.net_profit_growth": lambda s: _audit(s, "net_profit_growth"),
    "fin.gross_margin": lambda s: _audit(s, "gross_margin"),
    "fin.net_margin": lambda s: _audit(s, "net_margin"),
    "fin.roe": lambda s: _audit(s, "roe"),
    "fin.current_ratio": lambda s: _audit(s, "current_ratio"),
    "fin.debt_to_equity": lambda s: _audit(s, "debt_to_equity"),
    "fin.asset_turnover": lambda s: _audit(s, "asset_turnover"),
    "fin.earnings_quality": lambda s: _audit(s, "earnings_quality_score"),
    "fin.forensic_risk": lambda s: _audit(s, "forensic_risk"),
    "holders.top_name": lambda s: s.holders[0].get("shareholder_name") if s.holders else None,
    "holders.top_pct": lambda s: s.holders[0].get("percent") if s.holders else None,
    "holders.institutional_pct": lambda s: None,
    "queue.status": lambda s: s.queue.get("queue_status") if s.queue else None,
    "queue.days": lambda s: s.queue.get("queue_days_streak") if s.queue else None,
    "queue.distance": lambda s: s.queue.get("distance_to_limit") if s.queue else None,
    "div.last_date": lambda s: s.last_dividend,
    "signal.composite": lambda s: s.signal.get("composite_score") if s.signal else None,
}

#: ``flow.real_net`` is computed, not read — it needs several fields at once.
def _real_net(s: _Sources) -> Any:
    buy = _d(s, "buy_real_volume")
    sell = _d(s, "sell_real_volume")
    price = _d(s, "price_last") or _d(s, "price_close")
    if buy is None or sell is None or not price:
        return None
    return (float(buy) - float(sell)) * float(price)


_RESOLVERS["flow.real_net"] = _real_net


# ── instrument-module handles ───────────────────────────────────────────────────────
# Everything below reads a column that exists. What no column holds stays in
# PERMANENTLY_UNAVAILABLE, so a fund or contract sheet never shows a stock figure in its place.

def _nav_premium(s: _Sources) -> Any:
    """Premium or discount of the traded price over the last published NAV, in percent."""

    nav = (s.nav or {}).get("nav")
    price = _d(s, "price_last") or _d(s, "price_close")
    if not nav or not price:
        return None
    return (float(price) - float(nav)) / float(nav) * 100


_RESOLVERS.update({
    "nav.value": lambda s: (s.nav or {}).get("nav"),
    "nav.premium_pct": _nav_premium,
    "fund.nav_history": lambda s: len(s.nav_history) if s.nav_history else None,
    "fund.type": lambda s: (s.fund or {}).get("fund_type"),
    "fund.size": lambda s: (s.fund or {}).get("market_value"),
    "fund.units": lambda s: (s.fund or {}).get("shares_count"),
    "fund.liquidity": lambda s: (s.fund or {}).get("trade_value"),
    "option.underlying": lambda s: (s.option or {}).get("underlying"),
    "option.strike": lambda s: (s.option or {}).get("strike_price"),
    "option.expiry": lambda s: (s.option or {}).get("expiry_date"),
    "option.kind": lambda s: (s.option or {}).get("option_type"),
    "option.last": lambda s: (s.option or {}).get("price_last"),
    "option.volume": lambda s: (s.option or {}).get("trade_volume"),
    "future.expiry": lambda s: (s.future or {}).get("date_end"),
    "future.margin_initial": lambda s: (s.future or {}).get("margin_initial"),
    "future.margin_maintenance": lambda s: (s.future or {}).get("margin_maintenance"),
    "future.open_interest": lambda s: (s.future or {}).get("open_interest"),
})

#: Which payload gives the "as of" stamp for each key.
_AS_OF: dict[str, str] = {
    "detail": "date_update",
    "codal": "date_publish",
    "fin": "report_date",
    "holders": "date",
    "queue": "created_at",
    "div": "ex_date",
    "signal": "signal_date",
    "nav": "date",
    "fund": "snapshot_date",
}


class PreBuyEvidenceService:
    """Reads every evidence figure for one symbol in a single round of queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(
        self, symbol: str, catalogue: Mapping[str, Any] | None = None
    ) -> dict[str, EvidenceValue]:
        """Bind every declared handle for one symbol.

        ``catalogue`` is the evidence contract of the bank the sheet is judged against
        (``ResolvedBank.evidence_by_key()``); omitting it keeps the equity behaviour every
        existing caller depends on. A handle is checked against its own module's catalogue
        when the bank is composed, and anything this resolver has no binding for still comes
        back ``missing`` — never as a proxy value.
        """

        sources = await self._load(symbol)
        catalogue = catalogue if catalogue is not None else evidence_by_key()
        resolved: dict[str, EvidenceValue] = {}
        for key, meta in catalogue.items():
            reason = PERMANENTLY_UNAVAILABLE.get(key)
            value: Any = None
            if reason is None:
                resolver = _RESOLVERS.get(key)
                try:
                    value = resolver(sources) if resolver else None
                except Exception:  # defensive: one bad field must not kill the sheet
                    logger.debug("pre-buy evidence %s failed for %s", key, symbol, exc_info=True)
                    value = None
            resolved[key] = self._to_value(meta, value, sources, reason)
        return resolved

    @staticmethod
    def _to_value(meta: Any, value: Any, sources: _Sources, reason: str | None) -> EvidenceValue:
        if value in (None, "", [], {}):
            prefix = meta.key.split(".", 1)[0]
            why = reason or sources.errors.get(prefix) or "برای این نماد مقدار یافت نشد."
            return EvidenceValue(
                key=meta.key, label=meta.label, source=meta.source, unit=meta.unit,
                status="missing", note=why, declared=reason is not None,
            )
        return EvidenceValue(
            key=meta.key, label=meta.label, source=meta.source, unit=meta.unit,
            value=value if isinstance(value, (int, float, str)) else str(value),
            as_of=_as_of(meta.key, sources), status="available",
            note=reason or "",
        )

    async def _load(self, symbol: str) -> _Sources:
        """Read every source for one symbol.

        Sequential on purpose: an ``AsyncSession`` provisions a single connection and
        raises ``InvalidRequestError`` if two coroutines share it concurrently, so
        ``asyncio.gather`` over one session is a bug, not a speed-up. Each source still
        degrades independently — a missing payload becomes ``missing`` evidence, never a
        failed sheet.

        Each read runs inside a SAVEPOINT. Catching the exception is not enough on
        PostgreSQL: one failed statement aborts the whole transaction, so every later
        statement — including the sheet INSERT — would fail with
        ``InFailedSQLTransactionError``. The savepoint confines the damage to the source
        that actually broke.
        """

        src = _Sources()

        async def one(name: str, loader: Any) -> None:
            try:
                async with self.session.begin_nested():
                    value = await loader()
                setattr(src, name, value)
            except Exception as exc:
                src.errors[name] = f"خوانده نشد: {type(exc).__name__}"
                logger.debug("pre-buy source %s failed for %s", name, symbol, exc_info=True)

        await one("detail", lambda: self._enriched(symbol))
        await one("raw", lambda: self._raw_detail(symbol))
        await one("audit", lambda: self._audit(symbol))
        await one("holders", lambda: self._holders(symbol))
        await one("announcements", lambda: self._announcements(symbol))
        await one("report_count", lambda: self._report_count(symbol))
        await one("last_dividend", lambda: self._last_dividend(symbol))
        await one("queue", lambda: self._queue(symbol))
        await one("signal", lambda: self._signal(symbol))
        await one("fund", lambda: self._fund(symbol))
        await one("nav", lambda: self._nav_latest(symbol))
        await one("nav_history", lambda: self._nav_history(symbol))
        await one("option", lambda: self._contract(symbol))
        await one("future", lambda: self._future(symbol))
        return src

    async def _enriched(self, symbol: str) -> dict[str, Any] | None:
        from brsapi.services.query_service import BrsApiQueryService

        return await BrsApiQueryService(session=self.session).get_enriched_symbol_detail(symbol)

    async def _raw_detail(self, symbol: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                select(SymbolDetailModel)
                .where(SymbolDetailModel.symbol == symbol)
                .order_by(SymbolDetailModel.updated_at.desc().nullslast())
                .limit(1)
            )
        ).scalar_one_or_none()
        return _as_dict(row)

    async def _audit(self, symbol: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                select(CodalAuditSummaryModel).where(CodalAuditSummaryModel.symbol == symbol).limit(1)
            )
        ).scalar_one_or_none()
        return _as_dict(row)

    async def _holders(self, symbol: str) -> list[dict[str, Any]]:
        from brsapi.services.query_service import BrsApiQueryService

        return await BrsApiQueryService(session=self.session).get_shareholders(symbol)

    async def _announcements(self, symbol: str) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(CodalAnnouncementModel)
                .where(CodalAnnouncementModel.symbol == symbol)
                .order_by(CodalAnnouncementModel.date_publish.desc())
                .limit(40)
            )
        ).scalars().all()
        from brsapi.parsers.codal import detect_audit_status

        out = []
        for row in rows:
            item = _as_dict(row) or {}
            item["audit_status"] = detect_audit_status(str(item.get("title") or ""))
            out.append(item)
        return out

    async def _report_count(self, symbol: str) -> int:
        """True disclosure count — the list above is capped, so it must not be counted."""

        result = await self.session.execute(
            select(func.count()).select_from(CodalAnnouncementModel).where(
                CodalAnnouncementModel.symbol == symbol
            )
        )
        return int(result.scalar_one())

    async def _last_dividend(self, symbol: str) -> Any:
        """Latest recorded cash-dividend ex-date, or None when the ledger has no row."""

        return (
            await self.session.execute(
                select(func.max(CorporateActionModel.ex_date)).where(
                    CorporateActionModel.symbol == symbol,
                    CorporateActionModel.action_type == "dividend",
                )
            )
        ).scalar_one_or_none()

    async def _queue(self, symbol: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                select(QueueAnalysisResult)
                .where(QueueAnalysisResult.symbol == symbol)
                .order_by(QueueAnalysisResult.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return _as_dict(row)

    async def _signal(self, symbol: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                select(StockQuantSignalModel)
                .where(StockQuantSignalModel.symbol == symbol)
                .order_by(StockQuantSignalModel.signal_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return _as_dict(row)

    # ── non-equity sources ──────────────────────────────────────────────────────────
    # Each returns None when the symbol is not of that class, which the resolver reports as
    # «برای این نماد مقدار یافت نشد» — never as a figure borrowed from another instrument.

    async def _fund(self, symbol: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                select(FundModel).where(func.lower(FundModel.symbol) == symbol.lower()).limit(1)
            )
        ).scalars().first()
        return _as_dict(row)

    async def _nav_latest(self, symbol: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                select(NavRecordModel)
                .where(NavRecordModel.symbol == symbol)
                .order_by(desc(NavRecordModel.date))
                .limit(1)
            )
        ).scalars().first()
        return _as_dict(row)

    async def _nav_history(self, symbol: str) -> list[dict[str, Any]]:
        """How much NAV history exists for this symbol — the sheet says «چند رکورد»."""

        rows = (
            await self.session.execute(
                select(NavRecordModel)
                .where(NavRecordModel.symbol == symbol)
                .order_by(desc(NavRecordModel.date))
                .limit(250)
            )
        ).scalars().all()
        return [_as_dict(r) or {} for r in rows]

    async def _contract(self, symbol: str) -> dict[str, Any] | None:
        """Option terms from whichever contract table knows the symbol (stock or commodity)."""

        key = symbol.lower()
        stock = (
            await self.session.execute(
                select(StockOptionModel)
                .where(func.lower(StockOptionModel.symbol) == key)
                .order_by(desc(StockOptionModel.id))
                .limit(1)
            )
        ).scalars().first()
        if stock is not None:
            row = _as_dict(stock) or {}
            row.setdefault("underlying", row.get("underlying_symbol"))
            return row
        commodity = (
            await self.session.execute(
                select(CommodityOptionModel)
                .where(func.lower(CommodityOptionModel.symbol) == key)
                .order_by(desc(CommodityOptionModel.id))
                .limit(1)
            )
        ).scalars().first()
        return _as_dict(commodity)

    async def _future(self, symbol: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                select(ImeFutureModel)
                .where(func.lower(ImeFutureModel.contract_code) == symbol.lower())
                .order_by(desc(ImeFutureModel.id))
                .limit(1)
            )
        ).scalars().first()
        return _as_dict(row)


def _as_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {c.key: getattr(row, c.key, None) for c in row.__table__.columns}


def _as_of(key: str, sources: _Sources) -> str | None:
    prefix = key.split(".", 1)[0]
    field_name = _AS_OF.get(prefix)
    if field_name is None:
        return None
    bucket: Any
    if prefix == "detail":
        bucket = sources.detail or sources.raw
    elif prefix == "holders":
        bucket = sources.holders[0] if sources.holders else None
    elif prefix == "audit":
        bucket = sources.audit
    elif prefix == "codal":
        bucket = sources.announcements[0] if sources.announcements else None
    else:
        bucket = getattr(sources, prefix, None)
    if isinstance(bucket, dict):
        value = bucket.get(field_name)
        return str(value) if value else None
    return None


__all__ = ["PERMANENTLY_UNAVAILABLE", "PreBuyEvidenceService"]
