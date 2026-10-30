"""Phase 1 — data-terminal builders for GoldDesk.

Scope guard:
* No order, wallet, custody, delivery, or buy/sell route is created here.
* Phase 0 engine formulas are reused as-is through :mod:`pricer`.
* Every monetary value is Rial; BrsApi physical quotes are Toman and are
  converted explicitly with :func:`_toman_to_rial` before they reach a schema.

Fail-closed rule: a missing NAV, intrinsic input, composition, or contract
weight becomes ``None`` plus a Persian ``data_gaps`` entry — never zero and
never an estimate.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

import jdatetime
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.commodity import CommodityPriceModel, CurrencyPriceModel, GoldCoinPriceModel
from brsapi.models.ime import ImeCertificateModel, ImeFundModel
from brsapi.models.tsetmc import NavRecordModel

from . import pricer
from .constants import (
    COIN_MINTING_COSTS,
    COIN_WEIGHTS,
    GOLD_PURITY_18K,
    GOLD_PURITY_24K,
    GOLD_PURITY_COIN,
    MESGHAL_GRAMS,
    MINTING_COST_TOMAN,
    PRICE_LIVE_TTL_SECONDS,
    TROY_OUNCE_GRAMS,
)
from .phase1_schemas import (
    CertificateRow,
    FundRow,
    Phase1Quality,
    PhysicalRow,
    TerminalCapabilities,
    TerminalReferences,
    TerminalResponse,
    TickerItem,
    WhatIfFundEffect,
    WhatIfInputs,
    WhatIfPhysicalItem,
    WhatIfResponse,
)
from .snapshot_service import _as_utc

logger = logging.getLogger(__name__)

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

PhysicalBasis = Literal["gram", "mesghal", "coin"]

# The eight physical instruments the Phase 1 parity table must carry.
PHASE1_PHYSICAL: tuple[tuple[str, str, PhysicalBasis], ...] = (
    ("IR_GOLD_18K", "طلای ۱۸ عیار", "gram"),
    ("IR_GOLD_24K", "طلای ۲۴ عیار", "gram"),
    ("IR_GOLD_MELTED", "طلای آب‌شده (مثقالی)", "mesghal"),
    ("IR_COIN_EMAMI", "سکه امامی", "coin"),
    ("IR_COIN_BAHAR", "سکه بهار آزادی", "coin"),
    ("IR_COIN_HALF", "نیم سکه", "coin"),
    ("IR_COIN_QUARTER", "ربع سکه", "coin"),
    ("IR_COIN_1G", "سکه یک گرمی", "coin"),
)

_TICKER_SPECS: tuple[tuple[str, str, Literal["ounce", "rial"], str], ...] = (
    ("XAUUSD", "اونس جهانی طلا (XAU/USD)", "ounce", "brsapi_commodity_prices"),
    ("IR_GOLD_18K", "طلای ۱۸ عیار", "rial", "brsapi_gold_coin_prices"),
    ("USD", "دلار آزاد", "rial", "brsapi_currency_prices"),
)

# Silver/platinum funds are the ``1``-suffixed counterparts of a manager's gold
# fund (e.g. کهربا gold / نقران "کهربا1" silver). Verified against the live
# `brsapi_ime_funds` table on 2026-10-26; re-verify when the IME fund list grows.
_SILVER_TERMS = ("نقره", "نقر", "سیلو", "سیگ", "پلات", "پلاتین", "سیمین")
_PLACEHOLDER_SUFFIXES = {"2", "3", "4"}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive(value: Any) -> float | None:
    number = _num(value)
    return number if number is not None and number > 0 else None


def _int_or_none(value: Any) -> int | None:
    number = _num(value)
    return int(number) if number is not None else None


def _rial(value: float | None) -> float | None:
    if value is None:
        return None
    return float(pricer.round_to_rial(value, "rial"))


def _toman_to_rial(value: float | None) -> float | None:
    """BrsApi physical/currency quotes are Toman; Phase 1 promises Rial."""
    if value is None:
        return None
    return float(
        (Decimal(str(value)) * Decimal(10)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def _round_pct(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _round_usd(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _row_dict(row: Any) -> dict[str, Any]:
    table = getattr(row, "__table__", None)
    if table is None:
        return dict(row)
    return {column.name: getattr(row, column.name) for column in table.columns}


def _recency(row: Mapping[str, Any]) -> tuple[datetime, int, int]:
    stamp = _as_utc(row.get("fetched_at")) or _as_utc(row.get("created_at"))
    return (
        stamp or datetime.min.replace(tzinfo=UTC),
        int(row.get("time_unix") or 0),
        int(row.get("id") or 0),
    )


def _latest_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if not value:
            continue
        current = latest.get(str(value))
        if current is None or _recency(row) >= _recency(current):
            latest[str(value)] = dict(row)
    return latest


def _parse_jalali(date_text: Any, time_text: Any) -> datetime | None:
    """Convert a Shamsi date + time to a UTC datetime, or ``None``.

    Returning ``None`` is deliberate: silently substituting ``fetched_at`` as
    the observation time would let a stale NAV look fresher than it is.
    """
    if not date_text:
        return None
    text = str(date_text).translate(PERSIAN_DIGITS).strip().replace("/", "-")
    parts = text.split("-")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(part) for part in parts)
    except ValueError:
        return None
    time_value = str(time_text or "00:00:00").translate(PERSIAN_DIGITS).strip()
    time_parts = time_value.split(":")
    try:
        hour = int(time_parts[0]) if time_parts else 0
        minute = int(time_parts[1]) if len(time_parts) > 1 else 0
        second = int(float(time_parts[2])) if len(time_parts) > 2 else 0
        gregorian = jdatetime.date(year, month, day).togregorian()
        return datetime(
            gregorian.year,
            gregorian.month,
            gregorian.day,
            hour,
            minute,
            second,
            tzinfo=TEHRAN_TZ,
        ).astimezone(UTC)
    except (ValueError, TypeError):
        return None


def _freshness(as_of: datetime | None, now: datetime) -> Phase1Quality:
    if as_of is None:
        return "DELAYED"
    age = (now - as_of).total_seconds()
    if age < 0:
        return "DELAYED"
    return "LIVE" if age <= PRICE_LIVE_TTL_SECONDS else "DELAYED"


def _row_quality(price: float | None, as_of: datetime | None, now: datetime) -> Phase1Quality:
    if price is None or price <= 0:
        return "NO_DATA"
    return _freshness(as_of, now)


def _worst_quality(qualities: Iterable[Phase1Quality]) -> Phase1Quality:
    order: dict[str, int] = {
        "LIVE": 0,
        "DELAYED": 1,
        "SAMPLE": 2,
        "EDUCATIONAL": 3,
        "NO_DATA": 4,
    }
    values = list(qualities)
    return max(values, key=lambda value: order[value]) if values else "NO_DATA"


def _as_of_fetched(row: Mapping[str, Any] | None) -> datetime | None:
    return _as_utc(row.get("fetched_at")) if row else None


def _trade_value_rial(value: Any, unit: Any, gaps: list[str]) -> float | None:
    number = _num(value)
    if number is None:
        return None
    text = str(unit or "").strip()
    multiplier = 1.0
    if "هزار" in text:
        multiplier = 1_000.0
    elif "میلیون" in text:
        multiplier = 1_000_000.0
    elif "میلیارد" in text:
        multiplier = 1_000_000_000.0
    elif not text:
        gaps.append("واحد ارزش معاملات در منبع مشخص نیست")
    return _rial(number * multiplier)


def is_gold_fund(symbol: str, name: str | None) -> bool:
    """Return whether an IME commodity fund belongs in the gold-fund table.

    The IME feed publishes each gold commodity fund next to a ``1``-suffixed
    silver/platinum counterpart from the same manager. Symbol placeholders
    (``2``/``3``/``4``) are stale duplicate rows. Neither belongs in a gold
    table; deleting them is not our call, filtering them is.
    """
    symbol_text = str(symbol or "").translate(PERSIAN_DIGITS).strip()
    name_text = str(name or "").translate(PERSIAN_DIGITS).strip()
    if not symbol_text:
        return False
    if symbol_text[-1] in _PLACEHOLDER_SUFFIXES or symbol_text[-1].isdigit():
        return False
    if symbol_text.startswith(("نقر", "سیلو", "سیگ", "پلات", "سیمین")):
        return False
    if any(term in name_text for term in _SILVER_TERMS):
        return False
    return not name_text.endswith("1")


def _intrinsic(symbol: str, xau_usd: float | None, usd_irt_rial: float | None) -> float | None:
    if xau_usd is None or usd_irt_rial is None or xau_usd <= 0 or usd_irt_rial <= 0:
        return None
    try:
        value = pricer.fair_value(symbol, xau_usd, usd_irt_rial, unit="rial")
    except (ValueError, ZeroDivisionError):
        return None
    return _rial(value)


def _gold_grams_24k_equivalent(symbol: str) -> float | None:
    purity_18 = GOLD_PURITY_18K / GOLD_PURITY_24K
    if symbol == "IR_GOLD_18K":
        return purity_18
    if symbol == "IR_GOLD_24K":
        return 1.0
    if symbol == "IR_GOLD_MELTED":
        return MESGHAL_GRAMS * purity_18
    if symbol in COIN_WEIGHTS:
        return COIN_WEIGHTS[symbol] * (GOLD_PURITY_COIN / GOLD_PURITY_24K)
    return None


def _implied_usd(
    symbol: str, market_rial: float | None, usd_irt_rial: float | None
) -> float | None:
    """USD/oz implied by the asset's Rial market price at the given USD/IRR.

    This intentionally inverts the Phase 0 engine instead of re-deriving a
    second fair-value formula. Coins subtract their mint cost first.
    """
    if market_rial is None or usd_irt_rial is None or market_rial <= 0 or usd_irt_rial <= 0:
        return None
    gold_value = market_rial
    if symbol in COIN_WEIGHTS:
        mint_toman = COIN_MINTING_COSTS.get(symbol, MINTING_COST_TOMAN)
        gold_value -= _toman_to_rial(mint_toman) or 0.0
    grams_24k = _gold_grams_24k_equivalent(symbol)
    if grams_24k is None or grams_24k <= 0 or gold_value <= 0:
        return None
    return _round_usd(gold_value * TROY_OUNCE_GRAMS / (usd_irt_rial * grams_24k))


def _bubble(
    market_rial: float | None, intrinsic_rial: float | None
) -> tuple[float | None, float | None]:
    if market_rial is None or intrinsic_rial is None or intrinsic_rial <= 0:
        return None, None
    amount = market_rial - intrinsic_rial
    return _round_pct(amount / intrinsic_rial * 100.0), _rial(amount)


def _ticker_from_market(
    key: str,
    label: str,
    unit: Literal["ounce", "rial"],
    source_detail: str,
    row: Mapping[str, Any] | None,
    now: datetime,
) -> TickerItem:
    if row is None:
        return TickerItem(
            key=key,
            label=label,
            unit=unit,
            source_detail=source_detail,
            quality="NO_DATA",
            status="no_data",
            note="قیمت در منبع BrsApi موجود نیست",
        )
    raw_price = _positive(row.get("price"))
    raw_change = _num(row.get("change_value"))
    if key == "XAUUSD":
        price = _round_usd(raw_price)
        change = _round_usd(raw_change)
    else:
        price = _toman_to_rial(raw_price)
        change = _toman_to_rial(raw_change)
    as_of = _as_of_fetched(row)
    return TickerItem(
        key=key,
        label=label,
        price=price,
        unit=unit,
        change_pct=_round_pct(_num(row.get("change_percent"))),
        change_amount=change,
        as_of=as_of,
        source_detail=source_detail,
        quality=_row_quality(price, as_of, now),
        status="ok" if price is not None else "no_data",
        note=None if price is not None else "قیمت در منبع BrsApi موجود نیست",
    )


def build_ticker_items(
    market: Mapping[str, Mapping[str, Any]], *, now: datetime
) -> list[TickerItem]:
    items = [
        _ticker_from_market(key, label, unit, detail, market.get(key), now)
        for key, label, unit, detail in _TICKER_SPECS
    ]
    items.append(
        TickerItem(
            key="GOLD_FUND_INDEX",
            label="شاخص صندوق‌های طلا",
            unit="rial",
            source_detail="not_connected",
            quality="NO_DATA",
            status="under_construction",
            note="منبع شاخص رسمی صندوق‌های طلا متصل نیست — در دست ساخت",
        )
    )
    return items


def build_references(
    market: Mapping[str, Mapping[str, Any]], *, now: datetime
) -> TerminalReferences:
    xau_row = market.get("XAUUSD")
    usd_row = market.get("USD")
    xau = _positive(xau_row.get("price")) if xau_row else None
    usd_toman = _positive(usd_row.get("price")) if usd_row else None
    usd_rial = _toman_to_rial(usd_toman)
    xau_as_of = _as_of_fetched(xau_row)
    usd_as_of = _as_of_fetched(usd_row)
    gaps: list[str] = []
    if xau is None:
        gaps.append("XAU/USD در منبع BrsApi موجود نیست")
    if usd_rial is None:
        gaps.append("دلار آزاد در منبع BrsApi موجود نیست")
    stamps = [stamp for stamp in (xau_as_of, usd_as_of) if stamp is not None]
    as_of = min(stamps) if xau is not None and usd_rial is not None and len(stamps) == 2 else None
    quality = _worst_quality(
        [
            _row_quality(xau, xau_as_of, now),
            _row_quality(usd_rial, usd_as_of, now),
        ]
    )
    return TerminalReferences(
        xau_usd=_round_usd(xau),
        usd_irt_rial=usd_rial,
        as_of=as_of,
        quality=quality,
        data_gaps=gaps,
    )


def build_physical_row(
    symbol: str,
    label: str,
    basis: PhysicalBasis,
    row: Mapping[str, Any] | None,
    *,
    xau_usd: float | None,
    usd_irt_rial: float | None,
    ref_quality: Phase1Quality,
    now: datetime,
) -> PhysicalRow:
    gaps: list[str] = []
    price_toman = _positive(row.get("price")) if row else None
    price = _toman_to_rial(price_toman)
    as_of = _as_of_fetched(row)
    quality = _row_quality(price, as_of, now)
    intrinsic = _intrinsic(symbol, xau_usd, usd_irt_rial)
    intrinsic_quality: Phase1Quality = ref_quality if intrinsic is not None else "NO_DATA"
    bubble_pct, bubble_amount = _bubble(price, intrinsic)
    implied = _implied_usd(symbol, price, usd_irt_rial)

    change_amount = _toman_to_rial(_num(row.get("change_value"))) if row else None
    change_pct = _round_pct(_num(row.get("change_percent"))) if row else None

    if price is None:
        gaps.append("قیمت بازار در منبع BrsApi موجود نیست")
        change_amount = None
        change_pct = None
    elif row is not None and row.get("change_value") is None:
        gaps.append("تغییر روزانه در منبع BrsApi موجود نیست")
    if intrinsic is None:
        gaps.append("ارزش ذاتی محاسبه نشد: XAU/USD یا دلار آزاد موجود نیست")
    if bubble_pct is None and price is not None and intrinsic is not None:
        gaps.append("حباب محاسبه نشد")
    if implied is None and price is not None:
        gaps.append("USD ضمنی محاسبه نشد: نرخ دلار آزاد موجود نیست")

    return PhysicalRow(
        symbol=symbol,
        label=label,
        kind="coin" if symbol in COIN_WEIGHTS else "gold",
        price_basis=basis,
        price=price,
        change_pct=change_pct,
        change_amount=change_amount,
        intrinsic=intrinsic,
        bubble_pct=bubble_pct,
        bubble_amount=bubble_amount,
        implied_usd=implied,
        as_of=as_of,
        quality=quality,
        intrinsic_quality=intrinsic_quality,
        data_gaps=_dedupe(gaps),
    )


def build_fund_row(
    row: Mapping[str, Any], nav_row: Mapping[str, Any] | None, *, now: datetime
) -> FundRow:
    gaps: list[str] = []
    price_last = _positive(row.get("price_last"))
    price_close = _positive(row.get("price_close"))
    if price_last is not None:
        price = _rial(price_last)
        change_amount = _rial(_num(row.get("price_last_change")))
        change_pct = _round_pct(_num(row.get("price_last_change_pct")))
    elif price_close is not None:
        price = _rial(price_close)
        change_amount = _rial(_num(row.get("price_close_change")))
        change_pct = _round_pct(_num(row.get("price_close_change_pct")))
        gaps.append("قیمت آخرین معامله موجود نیست؛ قیمت پایانی نمایش داده می‌شود")
    else:
        price = None
        change_amount = None
        change_pct = None
        gaps.append("قیمت صندوق در منبع IME موجود نیست")

    last_trade_time = str(row.get("time")) if row.get("time") else None
    gaps.append("تاریخ معامله در منبع IME موجود نیست؛ فقط ساعت معامله ثبت شده است")

    volume = _int_or_none(row.get("trade_volume"))
    if volume is None:
        gaps.append("حجم معاملات در منبع IME موجود نیست")
    turnover = _rial(_num(row.get("trade_value")))
    if turnover is None:
        gaps.append("ارزش معاملات در منبع IME موجود نیست")
    market_cap = _rial(_num(row.get("market_value")))
    if market_cap is None:
        gaps.append("ارزش بازار در منبع IME موجود نیست")

    nav_issue = _positive(nav_row.get("nav_issue")) if nav_row else None
    nav_redemption = _positive(nav_row.get("nav_redemption")) if nav_row else None
    nav = nav_issue or nav_redemption
    nav_date = str(nav_row.get("date")) if nav_row and nav_row.get("date") else None
    nav_time = str(nav_row.get("time")) if nav_row and nav_row.get("time") else None
    nav_as_of = _parse_jalali(nav_date, nav_time)
    if nav is None:
        gaps.append("NAV در منبع brsapi_nav_records موجود نیست")
    elif nav_as_of is None:
        gaps.append("زمان NAV قابل تبدیل نبود؛ زمان دریافت منبع نمایش داده می‌شود")
        nav_as_of = _as_of_fetched(nav_row)
    if nav_issue is not None and nav_redemption is not None and nav_redemption > 0:
        divergence = abs(nav_issue - nav_redemption) / nav_redemption * 100.0
        if divergence >= 1.0:
            gaps.append("اختلاف NAV صدور و ابطال بیش از ۱٪ است")

    nominal_pct, nominal_amount = _bubble(price, nav)
    if nav is not None and price is not None and nominal_pct is None:
        gaps.append("حباب اسمی محاسبه نشد")

    if price is not None:
        gaps.append("حباب ذاتی نیاز به ترکیب دارایی صندوق دارد")
    gaps.append("حباب واقعی نیاز به ترکیب دارایی صندوق دارد")
    gaps.append("USD ضمنی صندوق نیاز به ترکیب دارایی و تعداد واحد دارد")

    as_of = _as_of_fetched(row)
    return FundRow(
        symbol=str(row.get("symbol")),
        name=str(row.get("name") or row.get("symbol")),
        price=price,
        change_pct=change_pct,
        change_amount=change_amount,
        last_trade_date=None,
        last_trade_time=last_trade_time,
        volume=volume,
        turnover=turnover,
        market_cap=market_cap,
        nav=_rial(nav),
        nav_issue=_rial(nav_issue),
        nav_redemption=_rial(nav_redemption),
        nav_date=nav_date,
        nav_time=nav_time,
        nav_as_of=nav_as_of,
        intrinsic_price=None,
        bubble_nominal_pct=nominal_pct,
        bubble_nominal_amount=nominal_amount,
        bubble_intrinsic_pct=None,
        bubble_intrinsic_amount=None,
        bubble_real_pct=None,
        composition=None,
        composition_status="needs_composition",
        implied_usd=None,
        as_of=as_of,
        quality=_row_quality(price, as_of, now),
        nav_quality=_row_quality(nav, nav_as_of, now),
        data_gaps=_dedupe(gaps),
    )


def build_certificate_row(row: Mapping[str, Any], *, now: datetime) -> CertificateRow:
    gaps: list[str] = []
    price = _rial(_positive(row.get("price_last")))
    if price is None:
        gaps.append("قیمت گواهی در منبع IME موجود نیست")
    change_amount = _rial(_num(row.get("price_last_change")))
    change_pct = _round_pct(_num(row.get("price_last_change_pct")))
    volume = _int_or_none(row.get("trade_volume"))
    if volume is None:
        gaps.append("حجم معاملات گواهی در منبع IME موجود نیست")
    turnover = _trade_value_rial(row.get("trade_value"), row.get("trade_value_unit"), gaps)
    if turnover is None:
        gaps.append("ارزش معاملات گواهی در منبع IME موجود نیست")

    date_text = row.get("date_update")
    time_text = row.get("time_update")
    source_as_of = _parse_jalali(date_text, time_text)
    as_of = source_as_of or _as_of_fetched(row)
    if date_text and source_as_of is None:
        gaps.append("تاریخ گواهی قابل تبدیل نبود؛ زمان دریافت منبع نمایش داده می‌شود")
    if not date_text:
        gaps.append("تاریخ معامله گواهی در منبع IME موجود نیست")

    gaps.append(
        "ارزش ذاتی گواهی محاسبه نشد: contract_size ضریب تبدیل انبار است، نه گرم"
    )
    gaps.append("برای ارزش ذاتی گواهی، وزن و عیار قرارداد لازم است")

    return CertificateRow(
        contract_code=str(row.get("contract_code")),
        commodity=row.get("commodity"),
        description=row.get("contract_description"),
        price=price,
        change_pct=change_pct,
        change_amount=change_amount,
        volume=volume,
        turnover=turnover,
        contract_size=_num(row.get("contract_size")),
        contract_size_unit=row.get("contract_size_unit"),
        intrinsic=None,
        bubble_pct=None,
        bubble_amount=None,
        implied_usd=None,
        as_of=as_of,
        source_date=str(date_text) if date_text else None,
        quality=_row_quality(price, as_of, now),
        intrinsic_quality="NO_DATA",
        data_gaps=_dedupe(gaps),
    )


async def _load_latest_market_rows(session: AsyncSession) -> dict[str, dict[str, Any]]:
    market: dict[str, dict[str, Any]] = {}
    physical_symbols = [symbol for symbol, _, _ in PHASE1_PHYSICAL]
    gold_rows = (
        await session.execute(
            select(GoldCoinPriceModel).where(GoldCoinPriceModel.symbol.in_(physical_symbols))
        )
    ).scalars().all()
    market.update(_latest_by((_row_dict(row) for row in gold_rows), "symbol"))

    commodity_rows = (
        await session.execute(
            select(CommodityPriceModel).where(
                CommodityPriceModel.symbol == "XAUUSD",
                CommodityPriceModel.category == "precious_metal",
            )
        )
    ).scalars().all()
    market.update(_latest_by((_row_dict(row) for row in commodity_rows), "symbol"))

    currency_rows = (
        await session.execute(select(CurrencyPriceModel).where(CurrencyPriceModel.symbol == "USD"))
    ).scalars().all()
    market.update(_latest_by((_row_dict(row) for row in currency_rows), "symbol"))
    return market


async def _load_latest_funds(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(ImeFundModel)
            .distinct(ImeFundModel.symbol)
            .order_by(
                ImeFundModel.symbol,
                desc(ImeFundModel.fetched_at),
                desc(ImeFundModel.id),
            )
        )
    ).scalars().all()
    latest = _latest_by(
        (_row_dict(row) for row in rows if is_gold_fund(row.symbol, row.name)), "symbol"
    )
    return sorted(
        latest.values(),
        key=lambda item: (-(item.get("market_value") or 0), str(item.get("symbol"))),
    )


async def _load_latest_navs(
    session: AsyncSession, symbols: list[str]
) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}
    rows = (
        await session.execute(
            select(NavRecordModel)
            .where(NavRecordModel.symbol.in_(symbols))
            .distinct(NavRecordModel.symbol)
            .order_by(
                NavRecordModel.symbol,
                desc(NavRecordModel.fetched_at),
                desc(NavRecordModel.id),
            )
        )
    ).scalars().all()
    return _latest_by((_row_dict(row) for row in rows), "symbol")


async def _load_latest_certificates(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(ImeCertificateModel)
            .where(
                or_(
                    ImeCertificateModel.contract_code.in_(("GoldBar", "GoldCoin")),
                    ImeCertificateModel.commodity.in_(("شمش طلا", "سکه طلا")),
                )
            )
            .distinct(ImeCertificateModel.contract_code)
            .order_by(
                ImeCertificateModel.contract_code,
                desc(ImeCertificateModel.fetched_at),
                desc(ImeCertificateModel.id),
            )
        )
    ).scalars().all()
    latest = _latest_by((_row_dict(row) for row in rows), "contract_code")
    return sorted(latest.values(), key=lambda item: str(item.get("contract_code")))


async def build_terminal(
    session: AsyncSession, *, now: datetime | None = None
) -> TerminalResponse:
    now = now or datetime.now(UTC)
    market = await _load_latest_market_rows(session)
    fund_market = await _load_latest_funds(session)
    navs = await _load_latest_navs(session, [str(item["symbol"]) for item in fund_market])
    certificates = await _load_latest_certificates(session)

    references = build_references(market, now=now)
    physical = [
        build_physical_row(
            symbol,
            label,
            basis,
            market.get(symbol),
            xau_usd=references.xau_usd,
            usd_irt_rial=references.usd_irt_rial,
            ref_quality=references.quality,
            now=now,
        )
        for symbol, label, basis in PHASE1_PHYSICAL
    ]
    funds = [
        build_fund_row(item, navs.get(str(item.get("symbol"))), now=now)
        for item in fund_market
    ]
    return TerminalResponse(
        generated_at=now,
        references=references,
        ticker=build_ticker_items(market, now=now),
        physical=physical,
        funds=funds,
        certificates=[build_certificate_row(item, now=now) for item in certificates],
        capabilities=TerminalCapabilities(),
    )


async def build_what_if(
    session: AsyncSession,
    xau_usd: float,
    usd_irt_rial: float,
    *,
    now: datetime | None = None,
) -> WhatIfResponse:
    """Pure preview: reads market data, writes nothing, never changes LIVE rows."""
    now = now or datetime.now(UTC)
    base = await build_terminal(session, now=now)
    physical: list[WhatIfPhysicalItem] = []
    for row in base.physical:
        preview_intrinsic = _intrinsic(row.symbol, xau_usd, usd_irt_rial)
        preview_pct, preview_amount = _bubble(row.price, preview_intrinsic)
        preview_implied = _implied_usd(row.symbol, row.price, usd_irt_rial)
        gaps = list(row.data_gaps)
        if preview_intrinsic is None:
            gaps.append("پیش‌نمایش ارزش ذاتی محاسبه نشد")
        if preview_implied is None and row.price is not None:
            gaps.append("پیش‌نمایش USD ضمنی محاسبه نشد")
        physical.append(
            WhatIfPhysicalItem(
                symbol=row.symbol,
                label=row.label,
                market_price=row.price,
                base_intrinsic=row.intrinsic,
                preview_intrinsic=preview_intrinsic,
                base_bubble_pct=row.bubble_pct,
                preview_bubble_pct=preview_pct,
                base_bubble_amount=row.bubble_amount,
                preview_bubble_amount=preview_amount,
                base_implied_usd=row.implied_usd,
                preview_implied_usd=preview_implied,
                quality=row.quality,
                preview_quality="SAMPLE",
                data_gaps=_dedupe(gaps),
            )
        )

    funds = [
        WhatIfFundEffect(
            symbol=row.symbol,
            name=row.name,
            nav=row.nav,
            market_price=row.price,
            nominal_bubble_pct_before=row.bubble_nominal_pct,
            nominal_bubble_pct_after=row.bubble_nominal_pct,
            real_bubble_pct_before=None,
            real_bubble_pct_after=None,
            implied_usd_before=None,
            implied_usd_after=None,
            data_gaps=_dedupe(
                list(row.data_gaps)
                + [
                    "حباب اسمی بر پایه NAV است و با XAU/USD تغییر نمی‌کند",
                    "حباب واقعی و USD ضمنی صندوق نیاز به ترکیب دارایی دارد",
                ]
            ),
        )
        for row in base.funds
    ]
    return WhatIfResponse(
        generated_at=now,
        inputs=WhatIfInputs(
            xau_usd=xau_usd,
            usd_irt_rial=usd_irt_rial,
            usd_irt_toman=float(Decimal(str(usd_irt_rial)) / Decimal(10)),
        ),
        physical=physical,
        funds=funds,
        capabilities=TerminalCapabilities(),
    )


__all__ = [
    "PHASE1_PHYSICAL",
    "build_certificate_row",
    "build_fund_row",
    "build_physical_row",
    "build_references",
    "build_terminal",
    "build_ticker_items",
    "build_what_if",
    "is_gold_fund",
]
