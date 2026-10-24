"""NAV Checker — P/NAV صندوق‌های طلا.

از brsapi_ime_funds + brsapi_nav_records می‌خواند. P/NAV + BPR + Inflow + 7d NAV change.

این تابع pure نیست — DB session لازم دارد.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import jdatetime
from core.time import now_tehran

from .dates import jalali_days_ago

logger = logging.getLogger(__name__)

# آخرین ردیف real/legal قدیمی‌تر از این تعداد روز «کهنه» تلقی می‌شود و BPR/Inflow
# آن صفر می‌ماند (audit GS-16) — پیش از این هیچ سقف تازگی اعمال نمی‌شد و نماد
# «عیار» با سه هفته تأخیر همان عدد را به امتیاز TSETMC می‌داد.
MAX_MARKET_DATA_AGE_DAYS: int = 7

# اختلاف نسبی NAV صدور و NAV ابطال که از آن به بعد «ناهمخوانی» باور می‌شود و
# لاگ می‌شود. واحد: درصد نسبت به NAV صدور. صفر یعنی همان NAV؛ مقدار کوچک طبیعی
# است، پس آستانه ۱٪ گرفته شده تا فقط شکاف واقعی گزارش شود (E-M3).
NAV_ISSUE_REDEMPTION_WARN_PCT: float = 1.0


@dataclass(frozen=True)
class FundNAVStatus:
    symbol: str
    fund_name: str
    nav_per_unit: float
    # None means "no traded price was found", which is not the same as a 0% bubble: the
    # scorer gives its best NAV mark to a zero, so substituting NAV here used to turn a
    # missing price into «تخفیف/نزدیک».
    market_price: float | None
    bubble_abs: float | None
    bubble_pct: float | None
    # None = نسبت خرید/فروش تعریف‌ناپذیر است (سمت فروش صفر/موجود نیست)، نه «۱ برابر».\n    # صفر سکوتی وزن ۱۸ امتیازی TSETMC را با «دادهٔ ناموجود» یکسان می‌کرد (E-M4).
    bpr: float | None
    real_buy_value: int
    real_sell_value: int
    net_inflow: int
    nav_7d_pct: float | None


def _resolve_nav(nav_issue: Any, nav_redemption: Any, label: str = "") -> float | None:
    """NAV مرجع را **صریحاً از nav_issue** برمی‌دارد و اختلافش با nav_redemption را گزارش می‌کند.

    انتخاب «اولین مقدار truthy» باعث می‌شد صندوقی که NAV صدورش تهی است بی‌سر‌و‌صدا
    با NAV ابطال قیمت‌گذاری شود و هیچ‌جا معلوم نشود دو NAV چقدر فاصله دارند (E-M3).
    """
    issue = float(nav_issue) if nav_issue else None
    redemption = float(nav_redemption) if nav_redemption else None
    if issue is not None and redemption is not None and issue > 0 and redemption > 0:
        diff_pct = abs(issue - redemption) / issue * 100.0
        if diff_pct >= NAV_ISSUE_REDEMPTION_WARN_PCT:
            logger.warning(
                "NAV issue/redemption divergence%s: issue=%.2f redemption=%.2f (%.2f%%, threshold %.2f%%)",
                f" for {label}" if label else "",
                issue,
                redemption,
                diff_pct,
                NAV_ISSUE_REDEMPTION_WARN_PCT,
            )
    if issue is not None and issue > 0:
        return issue
    return redemption


def _pick_nav(row: Any) -> float | None:
    """انتخاب مقدار NAV از ردیف ``(nav_issue, nav_redemption)``.

    ``brsapi_nav_records`` هیچ ستون ``nav`` ندارد؛ فقط ``nav_issue`` و
    ``nav_redemption``. انتخاب ستون اشتباه پیش‌تر در یک ``except Exception``
    بی‌صدا خورده می‌شد و برای هر ۱۰ صندوق طلا ``None`` برمی‌گرداند (GS-01).
    """
    if row is None:
        return None
    values = list(row)
    issue = values[0] if len(values) > 0 else None
    redemption = values[1] if len(values) > 1 else None
    return _resolve_nav(issue, redemption)


async def _latest_nav(session: AsyncSession, symbol: str) -> float | None:
    """آخرین NAV ثبت‌شده برای یک صندوق."""
    from brsapi.models import NavRecordModel

    stmt = (
        select(NavRecordModel.nav_issue, NavRecordModel.nav_redemption)
        .where(NavRecordModel.symbol == symbol)
        .order_by(desc(NavRecordModel.date))
        .limit(1)
    )
    result = await session.execute(stmt)
    return _pick_nav(result.first())


async def _nav_7d_ago(session: AsyncSession, symbol: str) -> float | None:
    """NAV ۷ روز قبل."""
    from brsapi.models import NavRecordModel

    # date در این جدول شمسی ذخیره می‌شود؛ cutoff هم باید شمسی باشد.
    cutoff = jalali_days_ago(7)
    stmt = (
        select(NavRecordModel.nav_issue, NavRecordModel.nav_redemption)
        .where(NavRecordModel.symbol == symbol, NavRecordModel.date <= cutoff)
        .order_by(desc(NavRecordModel.date))
        .limit(1)
    )
    result = await session.execute(stmt)
    return _pick_nav(result.first())


def _jalali_days_old(value: Any) -> int | None:
    """سنِ یک تاریخ شمسیِ ذخیره‌شده به **روز**؛ ``None`` اگر پارس نشود.

    مقایسهٔ رشته‌ای (``str(row.date) < cutoff``) به فرمت دقیق و صفرپیشوند وابسته
    بود؛ اگر منبع تاریخ را «۱۴۰۵-۷-۳» یا با اسلش می‌داد، سقف تازگی بی‌اثر می‌شد
    و دادهٔ ماه‌ها قبل مثل دادهٔ امروز در امتیاز می‌نشست (E-M5).
    """
    if value is None:
        return None
    parts = str(value).strip().replace("/", "-").split("-")
    if len(parts) != 3:
        logger.warning("unparsable jalali date %r", value)
        return None
    try:
        jalali = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (TypeError, ValueError):
        logger.warning("unparsable jalali date %r", value)
        return None
    return (now_tehran().date() - jalali.togregorian()).days


async def _fund_market_data(session: AsyncSession, symbol: str) -> dict[str, Any] | None:
    """آخرین اطلاعات بازار صندوق (real/legal volume)."""
    try:
        from brsapi.models.tsetmc import HistoricalRealLegalModel

        # استفاده از آخرین ردیف historical_real_legal
        stmt = (
            select(HistoricalRealLegalModel)
            .where(HistoricalRealLegalModel.symbol == symbol)
            .order_by(desc(HistoricalRealLegalModel.date))
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        # سقف تازگی: داده کهنه نباید مثل داده امروز در امتیاز TSETMC بنشیند.
        age_days = _jalali_days_old(row.date)
        if age_days is None or age_days > MAX_MARKET_DATA_AGE_DAYS:
            logger.warning(
                "stale real/legal data for %s: %s (%s days old, max %s)",
                symbol,
                row.date,
                age_days,
                MAX_MARKET_DATA_AGE_DAYS,
            )
            return None
        buy_val = int(row.buy_real_value or 0)
        sell_val = int(row.sell_real_value or 0)
        # سمت فروش صفر ⇒ نسبت تعریف‌ناپذیر است؛ ۰ برگرداندن یعنی «خریدار=فروشنده»
        # که کامپوننت TSETMC را با وزن کامل ۱۸ صفر امتیاز می‌کرد (E-M4).
        bpr = (buy_val / sell_val) if sell_val > 0 else None
        return {
            "buy_value": buy_val,
            "sell_value": sell_val,
            "bpr": bpr,
            "net_inflow": buy_val - sell_val,
        }
    except Exception as exc:  # noqa: BLE001
        # سکوت کامل این بلوک باعث می‌شد نبودِ جدول/ستون فقط با «BPR نیست» در
        # خروجی دیده شود و ریشه‌یابی غیرممکن باشد (E-L7).
        logger.warning("fund market data fetch failed for %s: %s", symbol, exc, exc_info=True)
        return None


async def get_fund_status(
    session: AsyncSession,
    symbol: str,
    market_price_override: float | None = None,
) -> FundNAVStatus | None:
    """وضعیت کامل یک صندوق.

    market_price_override: اگر قیمت بازار از BrsApi snapshot موجود باشد مستقیماً
        استفاده می‌شود؛ اگر هیچ‌کدام از منابع قیمت آن را ندهند، market_price None می‌ماند
        و حباب محاسبه نمی‌شود.
    """
    nav = await _latest_nav(session, symbol)
    if nav is None:
        return None

    if market_price_override is not None and market_price_override > 0:
        market_price = float(market_price_override)
    else:
        # تلاش برای خواندن قیمت بازار صندوق از BrsApi QueryService
        market_price = None
        with contextlib.suppress(Exception):
            from brsapi.services.query_service import BrsApiQueryService

            svc = BrsApiQueryService(session=session)
            # سعی 1: get_fund_prices اگر وجود دارد
            if hasattr(svc, "get_fund_prices"):
                rows = await svc.get_fund_prices()  # type: ignore
                for row in rows or []:
                    if row.get("symbol") == symbol and row.get("price"):
                        market_price = float(row["price"])
                        break
            # سعی 2: جدول مستقیم nav_records price?
            if market_price is None:
                # آخرین قیمت صندوق از GoldSnapshotModel اگر موجود باشد
                from sqlalchemy import desc, select

                from .models import GoldSnapshotModel

                stmt = (
                    select(GoldSnapshotModel.market_price)
                    .where(GoldSnapshotModel.symbol == symbol)
                    .order_by(desc(GoldSnapshotModel.snapshot_at))
                    .limit(1)
                )
                res = await session.execute(stmt)
                val = res.scalar()
                if val and float(val) > 0:
                    market_price = float(val)
        if market_price is not None and market_price <= 0:
            market_price = None

    market_data = await _fund_market_data(session, symbol) or {}
    bpr_raw = market_data.get("bpr")
    bpr = float(bpr_raw) if bpr_raw is not None else None
    buy_val = int(market_data.get("buy_value", 0))
    sell_val = int(market_data.get("sell_value", 0))
    net = int(market_data.get("net_inflow", 0))

    # NAV 7d
    nav_7d = await _nav_7d_ago(session, symbol)
    nav_7d_pct: float | None = None
    if nav_7d and nav_7d > 0:
        nav_7d_pct = ((nav - nav_7d) / nav_7d) * 100.0

    bubble_abs = None if market_price is None else market_price - nav
    bubble_pct = (
        None
        if bubble_abs is None or nav <= 0
        else bubble_abs / nav * 100.0
    )

    return FundNAVStatus(
        symbol=symbol,
        fund_name=symbol,
        nav_per_unit=nav,
        market_price=market_price,
        bubble_abs=bubble_abs,
        bubble_pct=bubble_pct,
        bpr=bpr,
        real_buy_value=buy_val,
        real_sell_value=sell_val,
        net_inflow=net,
        nav_7d_pct=nav_7d_pct,
    )


async def _latest_rows_by_symbol(session, model, columns, symbols, extra_where=None):
    """آخرین ردیف هر نماد را با **یک** کوئری برمی‌گرداند (batch).

    الگو: ``GROUP BY symbol`` روی `max(date)` در یک subquery و join به جدول اصلی.
    پیش‌تر ``get_all_funds_status`` برای هر صندوق ۴ کوئری می‌زد (N+1) و با ۱۰
    صندوق، ساخت snapshot را کند می‌کرد (E-L8).
    """
    if not symbols:
        return []
    conditions = [model.symbol.in_(list(symbols))]
    if extra_where is not None:
        conditions.append(extra_where)
    latest = (
        select(model.symbol.label("symbol"), func.max(model.date).label("max_date"))
        .where(*conditions)
        .group_by(model.symbol)
        .subquery()
    )
    stmt = select(*columns).join(
        latest,
        and_(model.symbol == latest.c.symbol, model.date == latest.c.max_date),
    )
    result = await session.execute(stmt)
    return result.all()


async def _latest_nav_batch(session: AsyncSession, symbols: list[str]) -> dict[str, float]:
    from brsapi.models import NavRecordModel

    rows = await _latest_rows_by_symbol(
        session,
        NavRecordModel,
        (NavRecordModel.symbol, NavRecordModel.nav_issue, NavRecordModel.nav_redemption),
        symbols,
    )
    out: dict[str, float] = {}
    for symbol, issue, redemption in rows:
        nav = _resolve_nav(issue, redemption, label=symbol)
        if nav is not None:
            out[symbol] = nav
    return out


async def _nav_7d_ago_batch(session: AsyncSession, symbols: list[str]) -> dict[str, float]:
    from brsapi.models import NavRecordModel

    rows = await _latest_rows_by_symbol(
        session,
        NavRecordModel,
        (NavRecordModel.symbol, NavRecordModel.nav_issue, NavRecordModel.nav_redemption),
        symbols,
        extra_where=NavRecordModel.date <= jalali_days_ago(7),
    )
    return {r[0]: _resolve_nav(r[1], r[2]) for r in rows}


async def _fund_market_data_batch(
    session: AsyncSession, symbols: list[str]
) -> dict[str, dict[str, Any]]:
    """BPR/جریان خالص همهٔ صندوق‌ها با یک کوئری + همان قاعدهٔ تازگی."""
    try:
        from brsapi.models.tsetmc import HistoricalRealLegalModel

        rows = await _latest_rows_by_symbol(
            session,
            HistoricalRealLegalModel,
            (
                HistoricalRealLegalModel.symbol,
                HistoricalRealLegalModel.date,
                HistoricalRealLegalModel.buy_real_value,
                HistoricalRealLegalModel.sell_real_value,
            ),
            symbols,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("fund market data batch fetch failed: %s", exc, exc_info=True)
        return {}

    out: dict[str, dict[str, Any]] = {}
    for symbol, row_date, buy_raw, sell_raw in rows:
        age_days = _jalali_days_old(row_date)
        if age_days is None or age_days > MAX_MARKET_DATA_AGE_DAYS:
            logger.warning(
                "stale real/legal data for %s: %s (%s days old, max %s)",
                symbol,
                row_date,
                age_days,
                MAX_MARKET_DATA_AGE_DAYS,
            )
            continue
        buy_val = int(buy_raw or 0)
        sell_val = int(sell_raw or 0)
        out[symbol] = {
            "buy_value": buy_val,
            "sell_value": sell_val,
            "bpr": (buy_val / sell_val) if sell_val > 0 else None,
            "net_inflow": buy_val - sell_val,
        }
    return out


async def _live_fund_prices(session: AsyncSession) -> dict[str, float]:
    """قیمت‌های لحظه‌ای صندوق‌ها از QueryService — یک بار برای همه، نهN بار."""
    prices: dict[str, float] = {}
    with contextlib.suppress(Exception):
        from brsapi.services.query_service import BrsApiQueryService

        svc = BrsApiQueryService(session=session)
        if hasattr(svc, "get_fund_prices"):
            for row in await svc.get_fund_prices() or []:  # type: ignore[misc]
                price = row.get("price")
                if row.get("symbol") and price and float(price) > 0:
                    prices[str(row["symbol"])] = float(price)
    return prices


async def _snapshot_prices_batch(session: AsyncSession, symbols: list[str]) -> dict[str, float]:
    """آخرین قیمت بازار ذخیره‌شده در snapshot قبلی — batch."""
    if not symbols:
        return {}
    from .models import GoldSnapshotModel

    latest = (
        select(
            GoldSnapshotModel.symbol.label("symbol"),
            func.max(GoldSnapshotModel.snapshot_at).label("max_at"),
        )
        .where(GoldSnapshotModel.symbol.in_(list(symbols)))
        .group_by(GoldSnapshotModel.symbol)
        .subquery()
    )
    stmt = select(GoldSnapshotModel.symbol, GoldSnapshotModel.market_price).join(
        latest,
        and_(
            GoldSnapshotModel.symbol == latest.c.symbol,
            GoldSnapshotModel.snapshot_at == latest.c.max_at,
        ),
    )
    result = await session.execute(stmt)
    out: dict[str, float] = {}
    for symbol, price in result.all():
        if price and float(price) > 0:
            out[str(symbol)] = float(price)
    return out


async def get_all_funds_status(
    session: AsyncSession,
    symbols: list[str],
    market_prices: dict[str, float] | None = None,
) -> list[FundNAVStatus]:
    """وضعیت همه صندوق‌های مورد نظر با تعداد کوئری ثابت (مستقل از تعداد نمادها).

    market_prices: دیکشنری symbol→market_price از snapshot BrsApi (اختیاری).
    """
    if not symbols:
        return []

    navs = await _latest_nav_batch(session, symbols)
    if not navs:
        return []

    nav_7d = await _nav_7d_ago_batch(session, [s for s in symbols if s in navs])
    market_data = await _fund_market_data_batch(session, [s for s in symbols if s in navs])

    prices: dict[str, float] = {
        sym: float(price)
        for sym, price in (market_prices or {}).items()
        if sym in navs and price and float(price) > 0
    }
    missing = [s for s in navs if s not in prices]
    if missing:
        prices.update({s: p for s, p in (await _live_fund_prices(session)).items() if s in missing})
        missing = [s for s in navs if s not in prices]
    if missing:
        prices.update(await _snapshot_prices_batch(session, missing))

    out: list[FundNAVStatus] = []
    for symbol in symbols:
        nav = navs.get(symbol)
        if nav is None:
            continue
        data = market_data.get(symbol) or {}
        buy_val = int(data.get("buy_value", 0))
        sell_val = int(data.get("sell_value", 0))
        net = int(data.get("net_inflow", 0))
        market_price = prices.get(symbol)

        nav_7d_value = nav_7d.get(symbol)
        nav_7d_pct: float | None = None
        if nav_7d_value and nav_7d_value > 0:
            nav_7d_pct = ((nav - nav_7d_value) / nav_7d_value) * 100.0

        bubble_abs = None if market_price is None else market_price - nav
        bubble_pct = None if bubble_abs is None or nav <= 0 else bubble_abs / nav * 100.0

        out.append(
            FundNAVStatus(
                symbol=symbol,
                fund_name=symbol,
                nav_per_unit=nav,
                market_price=market_price,
                bubble_abs=bubble_abs,
                bubble_pct=bubble_pct,
                bpr=data.get("bpr"),
                real_buy_value=buy_val,
                real_sell_value=sell_val,
                net_inflow=net,
                nav_7d_pct=nav_7d_pct,
            )
        )
    return out
