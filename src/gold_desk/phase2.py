"""Phase 2 — market coverage builders for GoldDesk.

Scope guard:
* No order, wallet, custody, delivery, checkout, or payment surface exists here.
  :class:`~.phase2_schemas.MarketCapabilities` states that on every response.
* Phase 0 formulas are reused through :mod:`pricer`; Phase 1 tables are reused
  through :func:`phase1.build_physical_row`, never re-derived.
* Every monetary value is Rial unless the field name ends in ``_usd``. BrsApi
  quote tables and the gold/coin history table store Toman for physical rows
  (``phase1._toman_to_rial``), but ``brsapi_gold_currency_pro_daily_history``
  stores FX closes (USD, AED, EUR) directly in **Rial** and XAU/USD in USD.
  Applying the Toman×10 conversion to FX history would inflate every earlier
  observation and fabricate a ~-90% "monthly" return, so the loaders take an
  explicit unit instead of assuming one.
* Fail-closed: a missing source yields ``None`` plus a Persian ``data_gaps``
  entry and ``source_status="not_connected"`` — never a synthetic price and
  never ``NaN``/``Infinity``.

Phase 2 has no persisted Tehran retail feed and no persisted online-platform
quote feed (verified against the live schema on 2026-10-26). Those two boards
therefore ship their full column set with ``NO_DATA`` rows rather than dropping
columns to hide the gap.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from urllib.parse import quote

import jdatetime
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.commodity import GoldCoinHistoryModel, GoldCurrencyProDailyHistoryModel
from brsapi.models.crypto import CryptoDailyHistoryModel, CryptoPriceModel
from brsapi.models.ime import ImeFundModel

from . import phase1, pricer
from .constants import TROY_OUNCE_GRAMS
from .phase1_schemas import PhysicalRow, TerminalReferences
from .phase2_schemas import (
    AssetReturnRow,
    CoverageStatus,
    FundMapCell,
    FundMapResponse,
    FundMapSummary,
    FundMapSummaryItem,
    MarketCapabilities,
    PeriodKey,
    PeriodReturn,
    PlatformQuote,
    PlatformsResponse,
    ReturnsMatrixResponse,
    SourceStatus,
    TehranBoardResponse,
    TehranRow,
)
from .portfolio_history import _to_gregorian
from .snapshot_service import _as_utc

logger = logging.getLogger(__name__)

PERIODS: tuple[PeriodKey, ...] = ("1m", "3m", "6m", "9m", "1y")
PERIOD_DAYS: dict[PeriodKey, int] = {"1m": 30, "3m": 91, "6m": 182, "9m": 273, "1y": 365}
# A period whose start observation is farther than this from the target start,
# or whose end observation is older than this, is reported as ``incomplete``.
MAX_START_GAP_DAYS = 14
MAX_END_AGE_DAYS = 14
# Currency conversion may interpolate over a short holiday gap, not over months.
MAX_CONVERSION_GAP_DAYS = 14

MIN_CORRELATION_OBS = 20
CORRELATION_MAX_OBS = 90
CORRELATION_WINDOW_DAYS = 365

# History loaders read a bounded calendar window instead of ``ORDER BY id DESC
# LIMIT n``: backfilled rows get high ids, so an id window mixed 2010 prices
# with 2026 prices and produced +26,000% "3-month" returns.
HISTORY_WINDOW_DAYS = 500
# A period may stretch past its nominal length by holidays and gaps, never by
# months: a 30-day return measured over 1,000 days is not a 1-month return.
MAX_PERIOD_STRETCH_DAYS = 30

_COVERAGE_ORDER: dict[str, int] = {"complete": 0, "incomplete": 1, "no_data": 2}


def _worst_status(*statuses: CoverageStatus) -> CoverageStatus:
    return max(statuses, key=lambda value: _COVERAGE_ORDER[value]) if statuses else "no_data"


def _finite(value: Any) -> float | None:
    number = phase1._num(value)
    if number is None or not math.isfinite(number):
        return None
    return number


def _finite_positive(value: Any) -> float | None:
    number = _finite(value)
    return number if number is not None and number > 0 else None


def _round_pct(value: float | None) -> float | None:
    rounded = phase1._round_pct(value)
    # ``-0.0`` (a self-conversion such as USD in USD) must not leak as a sign.
    return 0.0 if rounded == 0 else rounded


# ──────────────────────────────────────────────────────────────
#  Tehran shop / banking board
# ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TehranSpec:
    """One row of the Tehran retail/banking board.

    ``official_symbol`` points at the Phase 1 table the row is compared with;
    ``purity`` is the karat of a gram row (``None`` for coins, whose intrinsic
    comes from the Phase 0 coin formula).
    """

    key: str
    label: str
    kind: Literal["gold", "coin", "used", "exchange"]
    price_basis: Literal["gram", "coin"]
    purity: int | None
    official_symbol: str


TEHRAN_SPECS: tuple[TehranSpec, ...] = (
    TehranSpec("tehran_gold_18", "طلا گرم ۱۸ تهران", "gold", "gram", 18, "IR_GOLD_18K"),
    TehranSpec("tehran_gold_20", "طلا گرم ۲۰ تهران", "gold", "gram", 20, "IR_GOLD_18K"),
    TehranSpec("tehran_gold_21", "طلا گرم ۲۱ تهران", "gold", "gram", 21, "IR_GOLD_18K"),
    TehranSpec("tehran_gold_24", "طلا گرم ۲۴ تهران", "gold", "gram", 24, "IR_GOLD_24K"),
    TehranSpec("tehran_coin_emami", "سکه امامی تهران", "coin", "coin", None, "IR_COIN_EMAMI"),
    TehranSpec("tehran_coin_bahar", "سکه بهار تهران", "coin", "coin", None, "IR_COIN_BAHAR"),
    TehranSpec("tehran_coin_half", "نیم‌سکه تهران", "coin", "coin", None, "IR_COIN_HALF"),
    TehranSpec("tehran_coin_quarter", "ربع‌سکه تهران", "coin", "coin", None, "IR_COIN_QUARTER"),
    TehranSpec("tehran_coin_1g", "گرمی تهران", "coin", "coin", None, "IR_COIN_1G"),
    TehranSpec("tehran_used_18", "طلا ۱۸ دست‌دوم", "used", "gram", 18, "IR_GOLD_18K"),
    TehranSpec("tehran_exchange_18", "طلا ۱۸ تعویض", "exchange", "gram", 18, "IR_GOLD_18K"),
)

_TEHRAN_KIND_NOTES: dict[str, str] = {
    "used": "قیمت دست‌دوم شامل کارمزد و اختلاف خرید/فروش است؛ ارزش ذاتی با عیار ۱۸ محاسبه می‌شود.",
    "exchange": "قیمت تعویض شامل کارمزد تبدیل است؛ ارزش ذاتی با عیار ۱۸ محاسبه می‌شود.",
}


def _purity_ratio_karat(karat: int) -> float:
    """کسر عیار نسبت به ۲۴ عیار با همان تعریف موتور فاز ۰ (۲۴K = ۹۹۹.۹)."""
    if karat >= 24:
        return 1.0
    return pricer.purity_ratio(karat * 1000.0 / 24.0)


def _gram_intrinsic(spec: TehranSpec, xau_usd: float | None, usd_irt_rial: float | None) -> float | None:
    if xau_usd is None or usd_irt_rial is None or xau_usd <= 0 or usd_irt_rial <= 0:
        return None
    if spec.purity is None:
        return None
    try:
        if spec.purity >= 24:
            value = pricer.fair_gold_24k(xau_usd, usd_irt_rial)
        elif spec.purity == 18:
            value = pricer.fair_gold_18k(xau_usd, usd_irt_rial)
        else:
            value = pricer.base_24k_per_gram(xau_usd, usd_irt_rial) * _purity_ratio_karat(spec.purity)
    except (ValueError, ZeroDivisionError):
        return None
    return phase1._rial(value)


def _tehran_intrinsic(spec: TehranSpec, xau_usd: float | None, usd_irt_rial: float | None) -> float | None:
    if spec.price_basis == "coin":
        return phase1._intrinsic(spec.official_symbol, xau_usd, usd_irt_rial)
    return _gram_intrinsic(spec, xau_usd, usd_irt_rial)


def _tehran_implied_usd(spec: TehranSpec, price_rial: float | None, usd_irt_rial: float | None) -> float | None:
    if spec.price_basis == "coin":
        return phase1._implied_usd(spec.official_symbol, price_rial, usd_irt_rial)
    if price_rial is None or usd_irt_rial is None or price_rial <= 0 or usd_irt_rial <= 0:
        return None
    pure_gram = _purity_ratio_karat(spec.purity or 0)
    if pure_gram <= 0:
        return None
    return phase1._round_usd(price_rial * TROY_OUNCE_GRAMS / (usd_irt_rial * pure_gram))


def build_tehran_row(
    spec: TehranSpec,
    quote: Mapping[str, Any] | None,
    official: PhysicalRow | None,
    *,
    references: TerminalReferences,
    now: datetime,
) -> TehranRow:
    """Build one board row from an **already-Rial** quote and the Phase 1 row.

    ``quote["price_rial"]`` is Rial by contract; the adapter is responsible for
    the Toman→Rial conversion (there is no adapter yet — see
    :func:`_load_tehran_quotes`).
    """
    gaps: list[str] = []
    price = _finite_positive(quote.get("price_rial")) if quote else None
    as_of = _as_utc(quote.get("as_of")) if quote else None
    quality = phase1._row_quality(price, as_of, now)
    if price is None:
        gaps.append("قیمت خرده‌فروشی/بنکداری تهران در منبع متصل نیست")

    change_amount = _finite(quote.get("change_rial")) if quote else None
    change_pct = _round_pct(_finite(quote.get("change_pct"))) if quote else None
    if price is None:
        change_amount = None
        change_pct = None
    elif quote is not None and quote.get("change_rial") is None:
        gaps.append("تغییر روزانه در منبع تهران موجود نیست")

    intrinsic = _tehran_intrinsic(spec, references.xau_usd, references.usd_irt_rial)
    intrinsic_quality = references.quality if intrinsic is not None else "NO_DATA"
    if intrinsic is None:
        gaps.append("ارزش ذاتی محاسبه نشد: XAU/USD یا دلار آزاد موجود نیست")

    bubble_pct, bubble_amount = phase1._bubble(price, intrinsic)
    implied = _tehran_implied_usd(spec, price, references.usd_irt_rial)
    if implied is None and price is not None:
        gaps.append("USD ضمنی محاسبه نشد: نرخ دلار آزاد موجود نیست")

    official_price = official.price if official is not None else None
    if official_price is None:
        gaps.append("قیمت رسمی برای مقایسه در جدول فاز ۱ موجود نیست")
        spread_amount = None
        spread_pct = None
    elif price is None:
        spread_amount = None
        spread_pct = None
    else:
        spread_amount = phase1._rial(price - official_price)
        spread_pct = _round_pct((price - official_price) / official_price * 100.0) if official_price > 0 else None

    return TehranRow(
        key=spec.key,
        label=spec.label,
        kind=spec.kind,
        price_basis=spec.price_basis,
        purity=spec.purity,
        tehran_price=price,
        official_symbol=spec.official_symbol,
        official_label=official.label if official is not None else None,
        official_price=official_price,
        spread_vs_official_pct=spread_pct,
        spread_vs_official_amount=spread_amount,
        change_pct=change_pct,
        change_amount=change_amount,
        intrinsic=intrinsic,
        bubble_pct=bubble_pct,
        bubble_amount=bubble_amount,
        implied_usd=implied,
        as_of=as_of,
        source=str(quote.get("source") or "not_connected") if quote else "not_connected",
        source_detail=str(quote.get("source_detail") or "tehran_shop_feed") if quote else "tehran_shop_feed",
        quality=quality,
        intrinsic_quality=intrinsic_quality,
        note=_TEHRAN_KIND_NOTES.get(spec.kind),
        data_gaps=phase1._dedupe(gaps),
    )


def build_tehran_board(
    *,
    official_rows: Mapping[str, PhysicalRow],
    references: TerminalReferences,
    source_rows: Mapping[str, Mapping[str, Any]] | None = None,
    now: datetime,
) -> TehranBoardResponse:
    quotes = source_rows or {}
    rows = [
        build_tehran_row(
            spec,
            quotes.get(spec.key),
            official_rows.get(spec.official_symbol),
            references=references,
            now=now,
        )
        for spec in TEHRAN_SPECS
    ]
    priced = sum(1 for row in rows if row.tehran_price is not None)
    status: SourceStatus
    if priced == 0:
        status = "not_connected"
    elif priced < len(rows):
        status = "partial"
    else:
        status = "connected"
    return TehranBoardResponse(
        generated_at=now,
        references=references,
        source_status=status,
        rows=rows,
        capabilities=MarketCapabilities(),
    )


async def _load_tehran_quotes(_session: AsyncSession) -> dict[str, dict[str, Any]]:
    """Tehran retail/banking quotes — no persisted source exists.

    The live schema on 2026-10-26 has no table or column for Tehran shop,
    banking, used-gold, or exchange quotes, and the TGJU scraper publishes only
    ``geram18`` / coins / USD / AED / ounce. Rather than invent a price, this
    loader returns ``{}`` so the board keeps its full column set and reports
    ``source_status="not_connected"`` with a per-row gap. When a feed lands, it
    must return ``{spec.key: {"price_rial", "change_rial", "change_pct",
    "as_of", "source", "source_detail"}}`` with Rial-denominated prices.
    """
    return {}


async def load_tehran_board(session: AsyncSession, *, now: datetime | None = None) -> TehranBoardResponse:
    now = now or datetime.now(UTC)
    market = await phase1._load_latest_market_rows(session)
    references = phase1.build_references(market, now=now)
    official_rows: dict[str, PhysicalRow] = {}
    for symbol, label, basis in phase1.PHASE1_PHYSICAL:
        official_rows[symbol] = phase1.build_physical_row(
            symbol,
            label,
            basis,
            market.get(symbol),
            xau_usd=references.xau_usd,
            usd_irt_rial=references.usd_irt_rial,
            ref_quality=references.quality,
            now=now,
        )
    quotes = await _load_tehran_quotes(session)
    return build_tehran_board(
        official_rows=official_rows,
        references=references,
        source_rows=quotes,
        now=now,
    )


# ──────────────────────────────────────────────────────────────
#  Online platforms (price comparison only)
# ──────────────────────────────────────────────────────────────

PLATFORM_NOTICE = (
    "هیچ منبع قیمت زنده‌ای برای بسترهای آنلاین طلا متصل نیست؛ این بخش فقط "
    "مقایسهٔ قیمت است و هیچ مسیر خرید، پرداخت یا سفارشی ندارد. نام بسترها "
    "صرفاً ارجاع به منبع عمومی است و به معنی همکاری یا تأیید نیست."
)

PLATFORM_NOTICE_WITH_DATA = (
    "قیمت‌ها فقط اطلاعاتی هستند و از منبع نام‌برده شده‌اند؛ این صفحه هیچ مسیر "
    "خرید، سبد، پرداخت یا سفارشی ندارد و قیمت خرید/فروش الزاماً قابل معامله نیست."
)


def build_platform_row(raw: Mapping[str, Any], *, references: TerminalReferences, now: datetime) -> PlatformQuote:
    """One platform quote. Prices are per gram of 18k gold in Rial."""
    gaps: list[str] = []
    buy = _finite_positive(raw.get("buy_price_rial"))
    sell = _finite_positive(raw.get("sell_price_rial"))
    low = _finite_positive(raw.get("low_price_rial"))
    high = _finite_positive(raw.get("high_price_rial"))
    if buy is None and sell is None:
        gaps.append("قیمت خرید/فروش این بستر موجود نیست")
    if low is None or high is None:
        gaps.append("کمترین/بیشترین قیمت روز در منبع موجود نیست")

    intrinsic = phase1._intrinsic("IR_GOLD_18K", references.xau_usd, references.usd_irt_rial)
    if intrinsic is None:
        gaps.append("ارزش ذاتی ۱۸ عیار محاسبه نشد: XAU/USD یا دلار آزاد موجود نیست")
    market_price = buy if buy is not None else sell
    bubble_pct, _ = phase1._bubble(market_price, intrinsic)
    implied = phase1._implied_usd("IR_GOLD_18K", market_price, references.usd_irt_rial)
    if implied is None and market_price is not None:
        gaps.append("USD ضمنی محاسبه نشد")

    as_of = _as_utc(raw.get("as_of"))
    quality = phase1._row_quality(market_price, as_of, now)
    if quality != "NO_DATA":
        gaps.append("قیمت بستر ممکن است با کارمزد یا شرایط حساب متفاوت باشد")

    slug = str(raw.get("platform_slug") or raw.get("platform") or "").strip()
    return PlatformQuote(
        platform=str(raw.get("platform") or slug or "نامشخص"),
        platform_slug=slug,
        buy_price=buy,
        sell_price=sell,
        low_price=low,
        high_price=high,
        intrinsic_18k=intrinsic,
        bubble_pct=bubble_pct,
        implied_usd=implied,
        as_of=as_of,
        source=str(raw.get("source") or "not_connected"),
        source_detail=str(raw.get("source_detail") or "platform_quote_feed"),
        quality=quality,
        data_gaps=phase1._dedupe(gaps),
    )


def build_platforms(
    *,
    references: TerminalReferences,
    source_rows: Sequence[Mapping[str, Any]] | None = None,
    now: datetime,
) -> PlatformsResponse:
    raws = list(source_rows or [])
    rows = [build_platform_row(raw, references=references, now=now) for raw in raws]
    if not rows:
        status: SourceStatus = "not_connected"
        notice = PLATFORM_NOTICE
    else:
        priced = sum(1 for row in rows if row.buy_price is not None or row.sell_price is not None)
        status = "connected" if priced == len(rows) else "partial"
        notice = PLATFORM_NOTICE_WITH_DATA
    return PlatformsResponse(
        generated_at=now,
        source_status=status,
        platform_count=len(rows),
        rows=rows,
        notice=notice,
        capabilities=MarketCapabilities(),
    )


async def _load_platform_quotes(_session: AsyncSession) -> list[dict[str, Any]]:
    """Online-platform quotes — no persisted or licensed feed exists.

    Naming a platform in the UI requires a documented price source; without one
    this returns an empty list so the response is honest about the gap instead
    of shipping stale or scraped numbers. A future adapter must return
    ``[{"platform", "platform_slug", "buy_price_rial", "sell_price_rial",
    "low_price_rial", "high_price_rial", "as_of", "source",
    "source_detail"}]``.
    """
    return []


async def load_platforms(session: AsyncSession, *, now: datetime | None = None) -> PlatformsResponse:
    now = now or datetime.now(UTC)
    market = await phase1._load_latest_market_rows(session)
    references = phase1.build_references(market, now=now)
    quotes = await _load_platform_quotes(session)
    return build_platforms(references=references, source_rows=quotes, now=now)


# ──────────────────────────────────────────────────────────────
#  Returns matrix
# ──────────────────────────────────────────────────────────────

ASSET_SPECS: tuple[tuple[str, str, str, Literal["IRR", "USD"]], ...] = (
    ("coin_emami", "سکه امامی", "gold", "IRR"),
    ("gold_18k", "طلای ۱۸ عیار", "gold", "IRR"),
    ("usd", "دلار آمریکا", "currency", "IRR"),
    ("xau_usd", "انس طلا (XAU/USD)", "gold", "USD"),
    ("gold_fund_index", "شاخص صندوق‌های طلا (تقریبی)", "fund_index", "IRR"),
    ("tedpix", "کل بورس (شاخص کل)", "index", "IRR"),
    ("cpi", "تورم نقطه‌ای", "inflation", "IRR"),
    ("btc", "بیت‌کوین", "crypto", "USD"),
)

ASSET_SOURCES: dict[str, str] = {
    "coin_emami": "brsapi_gold_coin_history",
    "gold_18k": "brsapi_gold_coin_history",
    "usd": "brsapi_gold_currency_pro_daily_history",
    "xau_usd": "brsapi_gold_currency_pro_daily_history",
    "gold_fund_index": "brsapi_ime_funds (equal-weight approximation)",
    "tedpix": "brsapi_index_values (max per day — proxy)",
    "cpi": "not_connected",
    "btc": "brsapi_crypto_daily_history",
}

ASSET_GAPS: dict[str, list[str]] = {
    "gold_fund_index": ["شاخص رسمی صندوق‌های طلا وجود ندارد؛ این سری میانگین هم‌وزن بازده روزانهٔ صندوق‌های طلای IME است"],
    "tedpix": ["شاخص کل به‌صورت بیشترین مقدار شاخص منتشرشده در هر روز تقریب زده می‌شود (فرض مستند)"],
    "cpi": ["سری تورم نقطه‌ای (CPI) در پایگاه داده موجود نیست"],
    "xau_usd": ["تاریخچه XAU/USD در منبع روزانه به‌روز نمی‌شود؛ آخرین مشاهده ممکن است قدیمی باشد"],
}

MATRIX_METHOD = (
    "بازده سادهٔ نقطه‌به‌نقطه: (پایان/شروع − ۱)×۱۰۰. شروع هر دوره نزدیک‌ترین "
    "مشاهده به «پایان منهای طول دوره» است. تبدیل ریال↔دلار با بازده دلار/ریال "
    "در همان پنجرهٔ تاریخ انجام می‌شود. اگر مشاهدهٔ شروع بیش از ۱۴ روز با هدف "
    "فاصله داشته باشد یا آخرین مشاهده بیش از ۱۴ روز قدیمی باشد، بازه با برچسب "
    "«incomplete» و دلیل فارسی برمی‌گردد. اگر سری پیوسته نباشد و بازهٔ موجود از "
    "طول دوره بیش از ۳۰ روز بزرگ‌تر شود، بازده گزارش نمی‌شود (no_data)."
)


def _period_return(series: Mapping[date, float], period: PeriodKey, *, now: datetime) -> PeriodReturn:
    points = sorted(
        (day, value) for day, value in series.items() if value is not None and math.isfinite(value) and value > 0
    )
    if len(points) < 2:
        return PeriodReturn(
            period=period,
            status="no_data",
            observations=len(points),
            reason="سری زمانی کمتر از ۲ مشاهدهٔ معتبر دارد",
        )

    end_day, end_price = points[-1]
    target = end_day - timedelta(days=PERIOD_DAYS[period])
    start: tuple[date, float] | None = None
    for day, value in points:
        if day <= target:
            start = (day, value)
        else:
            break
    if start is None:
        return PeriodReturn(
            period=period,
            status="no_data",
            end_date=end_day,
            end_price=phase1._rial(end_price),
            observations=len(points),
            reason="سری زمانی به ابتدای دوره نمی‌رسد",
        )

    start_day, start_price = start
    span_days = (end_day - start_day).days
    if span_days > PERIOD_DAYS[period] + MAX_PERIOD_STRETCH_DAYS:
        return PeriodReturn(
            period=period,
            status="no_data",
            start_date=start_day,
            end_date=end_day,
            observations=sum(1 for day, _ in points if start_day <= day <= end_day),
            reason=(
                f"سری زمانی پیوسته نیست: بازهٔ موجود {span_days} روز است و دورهٔ "
                f"{PERIOD_DAYS[period]} روزه را پوشش نمی‌دهد؛ بازده گزارش نشد"
            ),
        )

    value = (end_price / start_price - 1.0) * 100.0
    reasons: list[str] = []
    if (target - start_day).days > MAX_START_GAP_DAYS:
        reasons.append(f"نزدیک‌ترین مشاهده به شروع دوره {(target - start_day).days} روز فاصله دارد")
    end_age = (now.date() - end_day).days
    if end_age > MAX_END_AGE_DAYS:
        reasons.append(f"آخرین مشاهده {end_age} روز قدیمی است")

    return PeriodReturn(
        period=period,
        value=_round_pct(value),
        status="incomplete" if reasons else "complete",
        start_date=start_day,
        end_date=end_day,
        start_price=phase1._rial(start_price),
        end_price=phase1._rial(end_price),
        observations=sum(1 for day, _ in points if start_day <= day <= end_day),
        reason="؛ ".join(reasons) or None,
    )


def _daily_returns(series: Mapping[date, float]) -> dict[date, float]:
    points = sorted(
        (day, value) for day, value in series.items() if value is not None and math.isfinite(value) and value > 0
    )
    out: dict[date, float] = {}
    for (_, previous), (day, current) in zip(points, points[1:], strict=False):
        out[day] = current / previous - 1.0
    return out


def _correlation(
    series: Mapping[date, float], benchmark: Mapping[date, float], *, now: datetime
) -> tuple[float | None, int, CoverageStatus, str | None]:
    cutoff = now.date() - timedelta(days=CORRELATION_WINDOW_DAYS)
    asset_returns = _daily_returns({day: value for day, value in series.items() if day >= cutoff})
    benchmark_returns = _daily_returns({day: value for day, value in benchmark.items() if day >= cutoff})
    common = sorted(set(asset_returns) & set(benchmark_returns))[-CORRELATION_MAX_OBS:]
    observations = len(common)
    if observations < MIN_CORRELATION_OBS:
        return (
            None,
            observations,
            "no_data",
            f"فقط {observations} بازده روز مشترک با دلار/ریال موجود است؛ حداقل {MIN_CORRELATION_OBS} لازم است",
        )
    xs = [asset_returns[day] for day in common]
    ys = [benchmark_returns[day] for day in common]
    mean_x = sum(xs) / observations
    mean_y = sum(ys) / observations
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    variance_x = sum((x - mean_x) ** 2 for x in xs)
    variance_y = sum((y - mean_y) ** 2 for y in ys)
    if variance_x <= 0 or variance_y <= 0:
        return None, observations, "no_data", "واریانس یکی از سری‌ها صفر است"
    return round(covariance / math.sqrt(variance_x * variance_y), 4), observations, "complete", None


def _value_at_or_before(series: Mapping[date, float], day: date) -> tuple[date, float] | None:
    found: tuple[date, float] | None = None
    for point_day, value in sorted(series.items()):
        if point_day <= day:
            found = (point_day, value)
        else:
            break
    return found


def _window_return(
    series: Mapping[date, float], start_day: date, end_day: date
) -> tuple[float | None, int | None, int | None]:
    start = _value_at_or_before(series, start_day)
    end = _value_at_or_before(series, end_day)
    if start is None or end is None or start[0] >= end[0] or start[1] <= 0:
        return None, None, None
    return (
        (end[1] / start[1] - 1.0) * 100.0,
        (start_day - start[0]).days,
        (end_day - end[0]).days,
    )


def _convert_period(
    native: PeriodReturn,
    *,
    native_currency: Literal["IRR", "USD"],
    base_currency: Literal["IRR", "USD"],
    usd_series: Mapping[date, float],
) -> PeriodReturn:
    """Convert one period return into the requested base currency.

    The USD/IRR return is measured over the *same window* as the native period
    (not over the USD row's own period), so an 87-day currency move can never be
    applied to a 30-day asset return.
    """
    if native_currency == base_currency:
        return native
    if native.value is None or native.start_date is None or native.end_date is None:
        return native

    usd_return, start_gap, end_gap = _window_return(usd_series, native.start_date, native.end_date)
    if usd_return is None:
        return PeriodReturn(
            period=native.period,
            status="no_data",
            start_date=native.start_date,
            end_date=native.end_date,
            observations=native.observations,
            reason="نرخ دلار/ریال در بازهٔ این دوره موجود نیست؛ تبدیل ارزی ممکن نشد",
        )

    reasons = [native.reason] if native.reason else []
    incomplete = (
        start_gap is None or end_gap is None or start_gap > MAX_CONVERSION_GAP_DAYS or end_gap > MAX_CONVERSION_GAP_DAYS
    )
    if start_gap is not None and start_gap > MAX_CONVERSION_GAP_DAYS:
        reasons.append(f"نرخ دلار در شروع دوره {start_gap} روز فاصله دارد")
    if end_gap is not None and end_gap > MAX_CONVERSION_GAP_DAYS:
        reasons.append(f"نرخ دلار در پایان دوره {end_gap} روز فاصله دارد")

    if base_currency == "USD":
        denominator = 1.0 + usd_return / 100.0
        if denominator <= 0:
            return PeriodReturn(
                period=native.period,
                status="no_data",
                start_date=native.start_date,
                end_date=native.end_date,
                observations=native.observations,
                reason="بازده دلار/ریال در این دوره نامعتبر است",
            )
        value = ((1.0 + native.value / 100.0) / denominator - 1.0) * 100.0
    else:
        value = ((1.0 + native.value / 100.0) * (1.0 + usd_return / 100.0) - 1.0) * 100.0

    status = _worst_status(native.status, "incomplete" if incomplete else "complete")
    return PeriodReturn(
        period=native.period,
        value=_round_pct(value),
        status=status,
        start_date=native.start_date,
        end_date=native.end_date,
        start_price=native.start_price,
        end_price=native.end_price,
        observations=native.observations,
        reason="؛ ".join(reason for reason in reasons if reason) or None,
    )


def build_returns_matrix_from_series(
    *,
    series: Mapping[str, Mapping[date, float]],
    base_currency: Literal["IRR", "USD"] = "IRR",
    extra_gaps: Mapping[str, Sequence[str]] | None = None,
    now: datetime,
) -> ReturnsMatrixResponse:
    """Pure matrix builder. ``series`` values are Rial (IRR assets) or USD (USD assets)."""
    usd_series = series.get("usd") or {}
    gaps_map = {key: list(value) for key, value in (extra_gaps or {}).items()}
    rows: list[AssetReturnRow] = []

    for key, label, asset_type, native_currency in ASSET_SPECS:
        native_series = series.get(key) or {}
        gaps = list(ASSET_GAPS.get(key, [])) + gaps_map.get(key, [])
        native_returns = {period: _period_return(native_series, period, now=now) for period in PERIODS}
        converted = {
            period: _convert_period(
                native_returns[period],
                native_currency=native_currency,
                base_currency=base_currency,
                usd_series=usd_series,
            )
            for period in PERIODS
        }

        if native_series:
            correlation, observations, correlation_status, correlation_reason = _correlation(
                native_series, usd_series, now=now
            )
        else:
            correlation, observations, correlation_status, correlation_reason = (
                None,
                0,
                "no_data",
                "سری زمانی این دارایی موجود نیست",
            )

        has_value = any(item.value is not None for item in converted.values())
        rows.append(
            AssetReturnRow(
                key=key,
                label=label,
                asset_type=asset_type,  # type: ignore[arg-type]
                native_currency=native_currency,
                returns=converted,
                correlation_90d=correlation,
                correlation_observations=observations,
                correlation_status=correlation_status,
                correlation_reason=correlation_reason,
                quality="DELAYED" if has_value else "NO_DATA",
                source=ASSET_SOURCES.get(key, "not_connected"),
                data_gaps=phase1._dedupe(gaps),
            )
        )

    return ReturnsMatrixResponse(
        generated_at=now,
        base_currency=base_currency,
        periods=list(PERIODS),
        correlation_against="USD/IRR",
        method=MATRIX_METHOD,
        rows=rows,
        capabilities=MarketCapabilities(),
    )


def _append_point(series: dict[date, float], point: tuple[date, float] | None) -> dict[date, float]:
    if point is None:
        return series
    day, value = point
    if value is None or not math.isfinite(value) or value <= 0:
        return series
    if not series or day > max(series):
        series[day] = value
    return series


def _history_window(now: datetime, days: int = HISTORY_WINDOW_DAYS) -> tuple[str, date]:
    """Jalali year floor for the SQL pre-filter plus the exact Gregorian cutoff.

    Date columns hold Jalali ``YYYY-MM-DD``/``YYYY/MM/DD`` strings, so a
    four-digit year prefix compares correctly in SQL. The Gregorian cutoff then
    drops anything that slips through a mixed-format column.
    """
    cutoff = (now - timedelta(days=days)).date()
    return str(jdatetime.date.fromgregorian(date=cutoff).year), cutoff


def _series_from_rows(
    rows: Iterable[Any],
    *,
    unit: Literal["toman", "rial", "usd"],
    cutoff: date | None = None,
) -> dict[date, float]:
    """Parse ``(date, close)`` rows into a dated series.

    ``unit="toman"`` applies the Phase 1 Toman→Rial conversion; ``"rial"`` and
    ``"usd"`` pass the value through untouched. Callers order rows newest-id
    first, so ``setdefault`` keeps the most recently ingested value per day.
    """
    series: dict[date, float] = {}
    for raw_day, raw_value in rows:
        day = _to_gregorian(raw_day)
        if day is None or (cutoff is not None and day < cutoff):
            continue
        value = _finite_positive(raw_value)
        if value is None:
            continue
        if unit == "toman":
            value = phase1._toman_to_rial(value)
        if value is None:
            continue
        series.setdefault(day, value)
    return series


async def _load_gold_history(
    session: AsyncSession, symbol: str, *, now: datetime, days: int = HISTORY_WINDOW_DAYS
) -> dict[date, float]:
    floor, cutoff = _history_window(now, days)
    try:
        rows = (
            await session.execute(
                select(GoldCoinHistoryModel.date, GoldCoinHistoryModel.price_close)
                .where(
                    GoldCoinHistoryModel.symbol == symbol,
                    GoldCoinHistoryModel.price_close.is_not(None),
                    GoldCoinHistoryModel.date != "",
                    GoldCoinHistoryModel.date >= floor,
                )
                .order_by(desc(GoldCoinHistoryModel.id))
                .limit(2000)
            )
        ).all()
    except Exception as exc:  # noqa: BLE001 — یک منبع خراب نباید کل ماتریس را ۵۰۰ کند
        logger.warning("gold history %s unavailable: %s", symbol, exc)
        return {}
    return _series_from_rows(rows, unit="toman", cutoff=cutoff)


async def _load_pro_history(
    session: AsyncSession,
    symbol: str,
    *,
    unit: Literal["rial", "usd"],
    now: datetime,
    days: int = HISTORY_WINDOW_DAYS,
) -> dict[date, float]:
    """FX closes here are Rial already (XAU/USD is USD); no Toman×10 applies."""
    floor, cutoff = _history_window(now, days)
    try:
        rows = (
            await session.execute(
                select(GoldCurrencyProDailyHistoryModel.date, GoldCurrencyProDailyHistoryModel.price_close)
                .where(
                    GoldCurrencyProDailyHistoryModel.symbol == symbol,
                    GoldCurrencyProDailyHistoryModel.price_close.is_not(None),
                    GoldCurrencyProDailyHistoryModel.date != "",
                    GoldCurrencyProDailyHistoryModel.date >= floor,
                )
                .order_by(desc(GoldCurrencyProDailyHistoryModel.id))
                .limit(2000)
            )
        ).all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("pro history %s unavailable: %s", symbol, exc)
        return {}
    return _series_from_rows(rows, unit=unit, cutoff=cutoff)


async def _load_crypto_history(
    session: AsyncSession, symbol: str, *, now: datetime, days: int = HISTORY_WINDOW_DAYS
) -> dict[date, float]:
    floor, cutoff = _history_window(now, days)
    try:
        rows = (
            await session.execute(
                select(CryptoDailyHistoryModel.date, CryptoDailyHistoryModel.price_close)
                .where(
                    CryptoDailyHistoryModel.symbol == symbol,
                    CryptoDailyHistoryModel.price_close.is_not(None),
                    CryptoDailyHistoryModel.date != "",
                    CryptoDailyHistoryModel.date >= floor,
                )
                .order_by(desc(CryptoDailyHistoryModel.id))
                .limit(2000)
            )
        ).all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("crypto history %s unavailable: %s", symbol, exc)
        return {}
    return _series_from_rows(rows, unit="usd", cutoff=cutoff)


_INDEX_SQL = text(
    """
    SELECT gregorian_date, MAX(index_value) AS value
    FROM brsapi_index_values
    WHERE (name = '' OR name = 'شاخص کل')
      AND index_value > 0
      AND gregorian_date IS NOT NULL
      AND gregorian_date >= :cutoff
    GROUP BY gregorian_date
    ORDER BY gregorian_date
    """
)


async def _load_index_series(
    session: AsyncSession, *, now: datetime, days: int = HISTORY_WINDOW_DAYS
) -> dict[date, float]:
    cutoff = (now - timedelta(days=days)).date()
    try:
        async with session.begin_nested():
            rows = (await session.execute(_INDEX_SQL, {"cutoff": cutoff})).all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("index series unavailable: %s", exc)
        return {}
    series: dict[date, float] = {}
    for raw_day, raw_value in rows:
        day = _to_gregorian(raw_day)
        value = _finite_positive(raw_value)
        if day is not None and value is not None:
            series[day] = value
    return series


async def _load_gold_fund_index(
    session: AsyncSession, *, now: datetime, days: int = HISTORY_WINDOW_DAYS
) -> dict[date, float]:
    """Equal-weight, daily-return-chained proxy for the gold-fund index.

    The feed has no official index, so this chains the equal-weight mean of
    per-fund daily returns from a base of 100 between consecutive IME snapshot
    dates. It is labelled as an approximation wherever it is used.
    """
    cutoff = (now - timedelta(days=days)).date().isoformat()
    try:
        rows = (
            await session.execute(
                select(
                    ImeFundModel.symbol,
                    ImeFundModel.name,
                    ImeFundModel.price_last,
                    ImeFundModel.price_close,
                    ImeFundModel.fetched_at,
                )
                .where(ImeFundModel.fetched_at >= cutoff)
                .order_by(desc(ImeFundModel.fetched_at), desc(ImeFundModel.id))
            )
        ).all()
    except Exception as exc:  # noqa: BLE001
        logger.warning("IME fund index unavailable: %s", exc)
        return {}

    by_symbol: dict[str, dict[date, float]] = {}
    for symbol, name, price_last, price_close, fetched_at in rows:
        if not phase1.is_gold_fund(str(symbol or ""), name):
            continue
        stamp = _as_utc(fetched_at)
        price = _finite_positive(price_last) or _finite_positive(price_close)
        if stamp is None or price is None:
            continue
        by_symbol.setdefault(str(symbol), {}).setdefault(stamp.date(), price)

    days_sorted = sorted({day for prices in by_symbol.values() for day in prices})
    levels: dict[date, float] = {}
    level = 100.0
    previous: date | None = None
    for day in days_sorted:
        has_prices = any(day in prices for prices in by_symbol.values())
        if not has_prices:
            continue
        if previous is None:
            levels[day] = level
        else:
            returns = [
                prices[day] / prices[previous] - 1.0
                for prices in by_symbol.values()
                if previous in prices and day in prices and prices[previous] > 0
            ]
            if returns:
                level *= 1.0 + sum(returns) / len(returns)
                levels[day] = level
        previous = day
    return levels


async def _load_current_prices(session: AsyncSession) -> dict[str, tuple[date, float]]:
    """Latest intraday quote per asset, keyed like the returns matrix."""
    out: dict[str, tuple[date, float]] = {}
    try:
        market = await phase1._load_latest_market_rows(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("current market rows unavailable: %s", exc)
        market = {}

    def add(key: str, row: Mapping[str, Any] | None, *, to_rial: bool) -> None:
        if not row:
            return
        price = _finite_positive(row.get("price"))
        stamp = phase1._as_of_fetched(row)
        if price is None or stamp is None:
            return
        value = phase1._toman_to_rial(price) if to_rial else price
        if value is not None and value > 0:
            out[key] = (stamp.date(), value)

    add("coin_emami", market.get("IR_COIN_EMAMI"), to_rial=True)
    add("gold_18k", market.get("IR_GOLD_18K"), to_rial=True)
    add("usd", market.get("USD"), to_rial=True)
    add("xau_usd", market.get("XAUUSD"), to_rial=False)

    try:
        row = (
            (
                await session.execute(
                    select(CryptoPriceModel)
                    .where(CryptoPriceModel.symbol == "BTC", CryptoPriceModel.price_usd.is_not(None))
                    .order_by(desc(CryptoPriceModel.id))
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("BTC current price unavailable: %s", exc)
        row = None
    if row is not None:
        stamp = _as_utc(row.fetched_at)
        price = _finite_positive(row.price_usd)
        if stamp is not None and price is not None:
            out["btc"] = (stamp.date(), price)
    return out


async def build_returns_matrix(
    session: AsyncSession,
    *,
    base_currency: Literal["IRR", "USD"] = "IRR",
    now: datetime | None = None,
) -> ReturnsMatrixResponse:
    now = now or datetime.now(UTC)
    current = await _load_current_prices(session)
    series: dict[str, dict[date, float]] = {
        "coin_emami": _append_point(
            await _load_gold_history(session, "IR_COIN_EMAMI", now=now), current.get("coin_emami")
        ),
        "gold_18k": _append_point(await _load_gold_history(session, "IR_GOLD_18K", now=now), current.get("gold_18k")),
        "usd": _append_point(await _load_pro_history(session, "USD", unit="rial", now=now), current.get("usd")),
        "xau_usd": _append_point(
            await _load_pro_history(session, "XAUUSD", unit="usd", now=now), current.get("xau_usd")
        ),
        "gold_fund_index": await _load_gold_fund_index(session, now=now),
        "tedpix": await _load_index_series(session, now=now),
        "btc": _append_point(await _load_crypto_history(session, "BTC", now=now), current.get("btc")),
    }
    return build_returns_matrix_from_series(series=series, base_currency=base_currency, now=now)


# ──────────────────────────────────────────────────────────────
#  Fund market map + market-value summary
# ──────────────────────────────────────────────────────────────


def _fund_cell(fund: Mapping[str, Any], size: float, total: float, *, now: datetime) -> FundMapCell:
    gaps: list[str] = []
    price_last = _finite_positive(fund.get("price_last"))
    price_close = _finite_positive(fund.get("price_close"))
    price = phase1._rial(price_last or price_close)
    if price is None:
        gaps.append("قیمت صندوق در منبع IME موجود نیست")
    change = _finite(fund.get("price_last_change_pct"))
    if change is None:
        change = _finite(fund.get("price_close_change_pct"))
    if change is None:
        gaps.append("تغییر روزانهٔ صندوق موجود نیست")
    symbol = str(fund.get("symbol") or "")
    if not symbol:
        gaps.append("نماد صندوق موجود نیست")
    share = size / total * 100.0 if total > 0 else None
    as_of = phase1._as_of_fetched(fund)
    return FundMapCell(
        symbol=symbol,
        name=str(fund.get("name") or symbol),
        size=size,
        size_share_pct=_round_pct(share),
        change_pct=_round_pct(change),
        price=price,
        quality=phase1._row_quality(price, as_of, now),
        as_of=as_of,
        href=f"/gold/terminal#fund-{quote(symbol, safe='')}" if symbol else "/gold/terminal",
        data_gaps=phase1._dedupe(gaps),
    )


def build_fund_map_from_funds(
    funds: Sequence[Mapping[str, Any]],
    *,
    size_metric: Literal["trade_value", "market_value"] = "trade_value",
    top_n: int = 10,
    now: datetime,
) -> FundMapResponse:
    """Pure fund-map builder. Non-finite or non-positive sizes never reach the UI."""
    sized: list[tuple[dict[str, Any], float]] = []
    for fund in funds:
        size = _finite_positive(fund.get(size_metric))
        if size is None:
            continue
        sized.append((dict(fund), size))
    sized.sort(key=lambda item: (-item[1], str(item[0].get("symbol") or "")))

    total = sum(size for _, size in sized)
    cells = [_fund_cell(fund, size, total, now=now) for fund, size in sized]

    top = sized[: max(1, int(top_n))]
    items = [
        FundMapSummaryItem(
            label=str(fund.get("name") or fund.get("symbol") or ""),
            symbol=str(fund.get("symbol")) if fund.get("symbol") else None,
            value=size,
            share_pct=_round_pct(size / total * 100.0) if total > 0 else None,
        )
        for fund, size in top
    ]
    other_value = sum(size for _, size in sized[len(top) :])
    return FundMapResponse(
        generated_at=now,
        size_metric=size_metric,
        cells=cells,
        summary=FundMapSummary(
            total_value=total,
            size_metric=size_metric,
            items=items,
            other_value=other_value,
            other_share_pct=_round_pct(other_value / total * 100.0) if total > 0 else None,
            cells_count=len(cells),
        ),
        capabilities=MarketCapabilities(),
    )


async def build_fund_map(
    session: AsyncSession,
    *,
    size_metric: Literal["trade_value", "market_value"] = "trade_value",
    top_n: int = 10,
    now: datetime | None = None,
) -> FundMapResponse:
    now = now or datetime.now(UTC)
    funds = await phase1._load_latest_funds(session)
    return build_fund_map_from_funds(funds, size_metric=size_metric, top_n=top_n, now=now)


__all__ = [
    "ASSET_SPECS",
    "PERIODS",
    "PLATFORM_NOTICE",
    "TEHRAN_SPECS",
    "TehranSpec",
    "build_fund_map",
    "build_fund_map_from_funds",
    "build_platform_row",
    "build_platforms",
    "build_returns_matrix",
    "build_returns_matrix_from_series",
    "build_tehran_board",
    "build_tehran_row",
    "load_platforms",
    "load_tehran_board",
]
