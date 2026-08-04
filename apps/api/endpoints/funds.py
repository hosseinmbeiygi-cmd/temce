"""
📊 Funds API — داده‌های صندوق‌های سرمایه‌گذاری بازار ایران

Endpoints:
  GET /funds                  — لیست همه صندوق‌ها (با فیلتر و مرتب‌سازی)
  GET /funds/{symbol}         — جزئیات یک صندوق
  GET /funds/types            — لیست انواع صندوق‌ها
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_brsapi_query_service, get_db_session
from brsapi.services.query_service import BrsApiQueryService
from core.logging import get_logger
from services.fund_service import FundService

logger = get_logger(__name__)
router = APIRouter()


def get_fund_service(db_session: AsyncSession = Depends(get_db_session)) -> FundService:
    """Factory dependency for FundService with proper DB session."""
    return FundService(session=db_session)

# ── Sample fund generator ──

_FUND_NAMES = [
    ("آگاس", "آتیه‌اندیشان اقتصاد پایدار", "اختصاصی"),
    ("آسامید", "آسمان توسعه ایرانیان", "اختصاصی"),
    ("آکاریز", "آگاه سرمایه ریز", "اهرمی"),
    ("آکشاورز", "آگاه کشاورز", "بخشی"),
    ("اسپید", "اسپیدار پارت", "اهرمی"),
    ("اشتیاق", "اشتیاق صبا", "درآمد ثابت"),
    ("اصنافی", "اعتبار صنعت و معدن", "اختصاصی"),
    ("اطلس", "اطلس سرمایه کیان", "اهرمی"),
    ("افتم", "افتخار همیشه سهام ایرانیان", "اهرمی"),
    ("اقبال", "اقبال یکم", "درآمد ثابت"),
    ("الماس", "الماس سرمد", "اختصاصی"),
    ("امید", "امید ایرانیان", "سهامی"),
    ("امین", "امین سرمایه پارس", "درآمد ثابت"),
    ("انرژی", "انرژی امید", "اختصاصی"),
    ("ایثار", "ایثار کارکنان بانک ملت", "اختصاصی"),
    ("ایرانیان", "صندوق سرمایه‌گذاری ایرانیان", "سهامی"),
    ("باپویا", "بانک پویا", "درآمد ثابت"),
    ("بدرخش", "بانک درخشش فردا", "اختصاصی"),
    ("باهنر", "بهمن اهتمام نوین رادین", "اختصاصی"),
    ("باور", "باور سرمایه", "اهرمی"),
    ("بدرخشان", "بانک درخشان", "اهرمی"),
    ("برکت", "برکت سهام", "سهامی"),
    ("بسامان", "بانک سامان", "درآمد ثابت"),
    ("بهینه", "بهینه پرداز", "اختصاصی"),
    ("پارسیان", "پارسیان سهام", "سهامی"),
    ("پدیده", "پدیده شفاف", "اهرمی"),
    ("پیشگامان", "پیشگامان سهام", "سهامی"),
    ("پویا", "پویا سرمایه", "اهرمی"),
    ("تابان", "تابان سهام", "بخشی"),
    ("تاپ", "تاپ سهام", "سهامی"),
    ("تدبیر", "تدبیرگران فردا", "اهرمی"),
    ("توسعه", "توسعه سهام", "سهامی"),
    ("ثابت", "ثابت سرمایه", "درآمد ثابت"),
    ("جامان", "جامان سهام", "سهامی"),
    ("جاوید", "جاوید سهم", "سهامی"),
    ("حافظ", "حافظ سهام", "سهامی"),
    ("خبرگان", "خبرگان سهام", "سهامی"),
    ("خرد", "خرد سهام", "سهامی"),
    ("دانش", "دانش بنیان", "اختصاصی"),
    ("دلیران", "دلیران سهام", "سهامی"),
    ("رادین", "رادین سهام", "سهامی"),
    ("رازی", "رازی سهام", "سهامی"),
    ("رفاه", "رفاه سهام", "اختصاصی"),
    ("سپهر", "سپهر سرمایه", "اهرمی"),
    ("ستاره", "ستاره سهام", "سهامی"),
    ("سدید", "سدید سهام", "سهامی"),
    ("سرآمد", "سرآمد سرمایه", "اهرمی"),
    ("سرمد", "سرمد سهام", "سهامی"),
    ("سپند", "سپند سرمایه", "اهرمی"),
    ("شفا", "شفا سهام", "بخشی"),
    ("صبا", "صبا سهام", "سهامی"),
    ("صنعت", "صنعت و معدن", "اختصاصی"),
    ("طلوع", "طلوع سهام", "سهامی"),
    ("عقیق", "عقیق سرمایه", "اهرمی"),
    ("فردا", "فردا سهام", "سهامی"),
    ("فیروزه", "فیروزه سهام", "اختصاصی"),
    ("ققنوس", "ققنوس سهام", "اهرمی"),
    ("کارآفرین", "کارآفرین سهام", "سهامی"),
    ("کامران", "کامران سهام", "سهامی"),
    ("کیوان", "کیوان سرمایه", "اهرمی"),
    ("گنجینه", "گنجینه سهام", "سهامی"),
    ("مبین", "مبین سرمایه", "اهرمی"),
    ("مثقال", "مثقال طلا", "بخشی"),
    ("محصول", "محصول کشاورزی", "بخشی"),
    ("مهر", "مهر سهام", "سهامی"),
    ("نادر", "نادر سهام", "سهامی"),
    ("ناهید", "ناهید سرمایه", "اهرمی"),
    ("نخل", "نخل طلا", "بخشی"),
    ("نیک", "نیک سهام", "سهامی"),
    ("وفاق", "وفاق سهام", "سهامی"),
    ("همراه", "همراه اول", "سهامی"),
    ("یسنا", "یسنا سهام", "سهامی"),
    ("گهر", "گهر انرژی", "سهامی"),
    ("زرفام", "زرین فام سرمایه", "اختصاصی"),
    ("نیرو", "نیرو سرمایه", "اهرمی"),
    ("دماوند", "دماوند سهام", "سهامی"),
    ("البرز", "البرز سهام", "سهامی"),
    ("آذین", "آذین سرمایه", "اهرمی"),
    ("بامداد", "بامداد سهام", "سهامی"),
    ("بهار", "بهار سهام", "سهامی"),
    ("پارمیدا", "پارمیدا سهام", "اختصاصی"),
]

_FUND_TYPES_PERSIAN: dict[str, str] = {
    "سهامی": "equity",
    "درآمد ثابت": "fixed_income",
    "اهرمی": "leveraged",
    "مختلط": "mixed",
    "بخشی": "sector",
    "اختصاصی": "special",
}


def _generate_fund(symbol: str, name: str, ftype: str) -> dict[str, Any]:
    """Generate realistic fund data."""
    base_nav = random.uniform(500, 50_000)
    change_pct = random.uniform(-4.0, 4.0)
    nav = round(base_nav, 0)
    nav_change = round(nav * change_pct / 100, 0)
    premium_discount = random.uniform(-0.03, 0.05)
    price_last = round(nav * (1 + premium_discount), 0)

    price_yesterday = round(price_last / (1 + change_pct / 100), 0)
    price_close = round(price_last * random.uniform(0.99, 1.01), 0)
    price_max = round(max(price_last, price_yesterday) * random.uniform(1.01, 1.04), 0)
    price_min = round(min(price_last, price_yesterday) * random.uniform(0.96, 0.99), 0)

    shares = random.randint(1_000_000, 200_000_000)
    volume = random.randint(10_000, 5_000_000)
    trade_value = round(volume * price_last, 0)
    trade_count = random.randint(10, 2000)
    market_value = round(shares * price_last, 0)

    buy_real = random.randint(0, int(volume * 0.7))
    sell_real = random.randint(0, int(volume * 0.7))
    buy_legal = random.randint(0, int(volume * 0.4))
    sell_legal = random.randint(0, int(volume * 0.4))

    isin = f"I{RANDOM_ISIN_SYMBOL}{str(random.randint(1000000, 9999999))}"

    return {
        "symbol": symbol,
        "name": name,
        "isin": isin,
        "fund_type": ftype,
        "nav": int(nav),
        "nav_change": int(nav_change),
        "nav_change_pct": round(change_pct, 2),
        "price_last": int(price_last),
        "price_close": int(price_close),
        "price_yesterday": int(price_yesterday),
        "price_max": int(price_max),
        "price_min": int(price_min),
        "trade_volume": volume,
        "trade_value": int(trade_value),
        "trade_count": trade_count,
        "shares_count": shares,
        "base_volume": int(shares * 0.01),
        "market_value": int(market_value),
        "buy_real_volume": buy_real,
        "buy_legal_volume": buy_legal,
        "sell_real_volume": sell_real,
        "sell_legal_volume": sell_legal,
        "time": datetime.now().strftime("%H:%M:%S"),
    }


RANDOM_ISIN_SYMBOL = "IR"


def _generate_all_funds() -> list[dict[str, Any]]:
    """Generate the full fund list."""
    random.seed(42)
    return [_generate_fund(sym, name, ftype) for sym, name, ftype in _FUND_NAMES]


_FUNDS_CACHE: list[dict[str, Any]] = []


def _get_funds() -> list[dict[str, Any]]:
    global _FUNDS_CACHE
    if not _FUNDS_CACHE:
        _FUNDS_CACHE = _generate_all_funds()
    return _FUNDS_CACHE


# ── Endpoints ──


@router.get("", summary="لیست همه صندوق‌ها")
async def list_funds(
    search: str | None = Query(None, description="جستجو در نام و نماد"),
    fund_type: str | None = Query(None, description="نوع صندوق (equity, fixed_income, leveraged, mixed, sector, special)"),
    min_nav_change: float | None = Query(None, description="حداقل درصد تغییر NAV"),
    sort_by: str = Query("nav", description="مرتب‌سازی بر اساس (nav, nav_change_pct, trade_volume, market_value, symbol)"),
    sort_desc: bool = Query(True, description="نزولی؟"),
    limit: int = Query(100, ge=1, le=500, description="تعداد نتایج"),
    offset: int = Query(0, ge=0, description="شروع از"),
    fund_service: FundService = Depends(get_fund_service),
) -> dict[str, Any]:
    """
    دریافت لیست همه صندوق‌های سرمایه‌گذاری با امکان فیلتر و مرتب‌سازی.

    - **search**: عبارت جستجو در نماد یا نام صندوق
    - **fund_type**: فیلتر بر اساس نوع صندوق (equity, fixed_income, leveraged, mixed, sector, special)
    - **min_nav_change**: حداقل درصد تغییر NAV
    - **sort_by**: مرتب‌سازی (nav, nav_change_pct, trade_volume, market_value, symbol)
    - **sort_desc**: نزولی؟
    - **limit**: حداکثر تعداد نتایج
    - **offset**: شروع از
    """
    funds = _get_funds()

    # ── Filter ──
    if search:
        s = search.strip().lower()
        funds = [f for f in funds if s in f["symbol"].lower() or s in f["name"].lower()]

    if fund_type:
        funds = [f for f in funds if _FUND_TYPES_PERSIAN.get(f.get("fund_type", "")) == fund_type]

    if min_nav_change is not None:
        funds = [f for f in funds if (f.get("nav_change_pct") or 0) >= min_nav_change]

    # ── Sort ──
    sort_field_map = {
        "nav": "nav",
        "nav_change_pct": "nav_change_pct",
        "trade_volume": "trade_volume",
        "market_value": "market_value",
        "symbol": "symbol",
    }
    field = sort_field_map.get(sort_by, "nav")
    funds.sort(key=lambda f: f.get(field, 0) or 0, reverse=sort_desc)

    total = len(funds)
    funds = funds[offset: offset + limit]

    # ── Types breakdown ──
    type_counts: dict[str, int] = {}
    for f in _get_funds():
        ft = f.get("fund_type", "ساير")
        type_counts[ft] = type_counts.get(ft, 0) + 1

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": funds,
        "type_counts": type_counts,
    }


@router.get("/types", summary="لیست انواع صندوق‌ها")
async def list_fund_types() -> list[dict[str, str]]:
    """
    دریافت لیست انواع صندوق‌های سرمایه‌گذاری با کلید انگلیسی و نام فارسی.
    """
    return [
        {"key": "equity", "label": "سهامی"},
        {"key": "fixed_income", "label": "درآمد ثابت"},
        {"key": "leveraged", "label": "اهرمی"},
        {"key": "mixed", "label": "مختلط"},
        {"key": "sector", "label": "بخشی"},
        {"key": "special", "label": "اختصاصی"},
    ]


@router.get("/{symbol}", summary="جزئیات یک صندوق")
async def get_fund(symbol: str) -> dict[str, Any]:
    """
    دریافت اطلاعات کامل یک صندوق سرمایه‌گذاری.

    - **symbol**: نماد صندوق (مثلاً \"فولاد\")
    """
    funds = _get_funds()
    for f in funds:
        if f["symbol"] == symbol:
            # Add analysis prediction without mutating cache
            score = _compute_fund_score(f)
            return {**f, "analysis": score}

    return {
        "symbol": symbol,
        "error": f"صندوق با نماد {symbol} یافت نشد",
    }


@router.post("/{symbol}/update", summary="به‌روزرسانی داده‌های صندوق از BrsApi")
async def update_fund_from_brsapi(
    symbol: str,
    fund_service: FundService = Depends(get_fund_service),
    brsapi: BrsApiQueryService = Depends(get_brsapi_query_service),
) -> dict[str, Any]:
    """
    دریافت داده‌های لحظه‌ای یک صندوق از BrsApi و ذخیره در دیتابیس.

    - **symbol**: نماد صندوق (مثلاً \"آگاس\")

    اگر صندوق قبلاً در دیتابیس وجود داشته باشد، داده‌های آن به‌روز می‌شود.
    در غیر این صورت، صندوق جدیدی ایجاد می‌شود.

    داده‌های دریافتی:
      - قیمت‌ها (last, close, yesterday, max, min)
      - حجم و ارزش معاملات
      - تعداد معاملات
      - خرید/فروش حقیقی و حقوقی
      - NAV محاسبه‌شده
    """
    return await fund_service.update_from_brsapi(
        symbol=symbol,
        brsapi=brsapi,
    )


@router.get("/{symbol}/analysis", summary="تحلیل هوشمند یک صندوق")
async def get_fund_analysis(symbol: str) -> dict[str, Any]:
    """
    تحلیل کامل یک صندوق بر اساس ۶ بعد:
    مالی، نقدشوندگی، مدیریت، ریسک، هزینه، شفافیت

    - **symbol**: نماد صندوق (مثلاً \"آگاس\")
    """
    funds = _get_funds()
    fund = None
    for f in funds:
        if f["symbol"] == symbol:
            fund = f
            break

    if not fund:
        return {"symbol": symbol, "error": f"صندوق با نماد {symbol} یافت نشد"}

    return _compute_full_analysis(fund)


# ── Internal helpers ──


def _compute_fund_score(f: dict[str, Any]) -> dict[str, Any]:
    """Quick score recomputation for a fund (mimicking frontend logic)."""
    score = 60  # base

    if f.get("nav_change_pct", 0) > 1:
        score += 20
    elif f.get("nav_change_pct", 0) > 0:
        score += 5
    elif f.get("nav_change_pct", 0) < -1:
        score -= 10

    if f.get("trade_volume", 0) > 1_000_000:
        score += 15
    elif f.get("trade_volume", 0) > 100_000:
        score += 5
    else:
        score -= 10

    if f.get("market_value", 0) > 1_000_000_000_000:
        score += 10
    elif f.get("market_value", 0) < 50_000_000_000:
        score -= 5

    return {
        "score": max(0, min(100, score)),
        "recommendation": "BUY" if score >= 70 else "WATCHLIST" if score >= 55 else "HOLD" if score >= 40 else "AVOID",
    }


def _compute_full_analysis(f: dict[str, Any]) -> dict[str, Any]:
    """Full 6-dimension fund analysis matching the frontend engine."""

    # Financial
    financial = 60
    if f.get("nav_change_pct", 0) > 1:
        financial += 20
    elif f.get("nav_change_pct", 0) > 0.5:
        financial += 10
    elif f.get("nav_change_pct", 0) > 0:
        financial += 5
    elif f.get("nav_change_pct", 0) < -0.5:
        financial -= 15
    if f.get("nav", 0) > 10000:
        financial += 5
    if f.get("trade_count", 0) > 100:
        financial += 5
    financial = max(0, min(100, financial))

    # Liquidity
    liquidity = 50
    if f.get("trade_volume", 0) > 1_000_000:
        liquidity += 30
    elif f.get("trade_volume", 0) > 500_000:
        liquidity += 20
    elif f.get("trade_volume", 0) > 100_000:
        liquidity += 10
    else:
        liquidity -= 15
    if f.get("trade_value", 0) > 1_000_000_000:
        liquidity += 10
    elif f.get("trade_value", 0) > 100_000_000:
        liquidity += 5
    else:
        liquidity -= 5
    if f.get("trade_count", 0) > 500:
        liquidity += 10
    elif f.get("trade_count", 0) > 100:
        liquidity += 5
    elif f.get("trade_count", 0) < 10:
        liquidity -= 10
    liquidity = max(0, min(100, liquidity))

    # Management
    management = 65
    if f.get("shares_count", 0) > 50_000_000:
        management += 20
    elif f.get("shares_count", 0) > 10_000_000:
        management += 10
    elif f.get("shares_count", 0) < 1_000_000:
        management -= 15
    if f.get("market_value", 0) > 1_000_000_000_000:
        management += 10
    elif f.get("market_value", 0) > 100_000_000_000:
        management += 5
    else:
        management -= 5
    net_legal = (f.get("buy_legal_volume", 0) or 0) - (f.get("sell_legal_volume", 0) or 0)
    if net_legal > 0:
        management += 5
    management = max(0, min(100, management))

    # Risk
    risk = 60
    price_range = (f.get("price_max", 0) or 0) - (f.get("price_min", 0) or 0)
    avg_price = ((f.get("price_max", 0) or 0) + (f.get("price_min", 0) or 0)) / 2
    if avg_price > 0:
        range_pct = price_range / avg_price
        if range_pct < 0.01:
            risk += 15
        elif range_pct < 0.03:
            risk += 10
        elif range_pct < 0.05:
            risk += 5
        elif range_pct > 0.10:
            risk -= 10
    if f.get("nav_change_pct", 0) < -2:
        risk -= 15
    elif f.get("nav_change_pct", 0) < -1:
        risk -= 10
    elif f.get("nav_change_pct", 0) < -0.5:
        risk -= 5
    if f.get("trade_volume", 0) > 500_000:
        risk += 5
    risk = max(0, min(100, risk))

    # Cost
    cost = 70
    if (f.get("price_last", 0) or 0) > 0 and (f.get("nav", 0) or 0) > 0:
        premium = ((f["price_last"] - f["nav"]) / f["nav"]) * 100
        if premium > 5:
            cost -= 15
        elif premium > 2:
            cost -= 5
        elif premium > 0:
            cost -= 2
    if f.get("trade_count", 0) > 1000:
        cost -= 5
    elif f.get("trade_count", 0) < 10:
        cost += 5
    cost = max(0, min(100, cost))

    # Transparency
    transparency = 65
    if f.get("isin", "") and len(f.get("isin", "")) > 5:
        transparency += 15
    if f.get("price_yesterday", 0) > 0:
        transparency += 5
    if (f.get("price_max", 0) or 0) > 0 and (f.get("price_min", 0) or 0) > 0:
        transparency += 5
    if len(f.get("name", "")) > 3:
        transparency += 5
    if (f.get("buy_real_volume", 0) or 0) > 0 or (f.get("buy_legal_volume", 0) or 0) > 0:
        transparency += 5
    transparency = max(0, min(100, transparency))

    # Total
    total = (
        financial * 0.25
        + liquidity * 0.20
        + management * 0.18
        + risk * 0.15
        + cost * 0.12
        + transparency * 0.10
    )
    total = max(0, min(100, round(total)))

    # Recommendation
    if total >= 80 and risk >= 50:
        rec = "STRONG_BUY"
    elif total >= 70:
        rec = "BUY"
    elif total >= 60:
        rec = "WATCHLIST"
    elif total >= 50:
        rec = "HOLD"
    elif total >= 35:
        rec = "REDUCE"
    else:
        rec = "AVOID"

    # Risk level
    issues_count = 0
    for check, inc in [
        (f.get("nav_change_pct", 0) < -2, 1),
        (f.get("trade_volume", 0) < 100_000, 1),
        (f.get("market_value", 0) < 50_000_000_000, 1),
        (financial < 50, 1),
        (liquidity < 40, 1),
    ]:
        if check:
            issues_count += inc

    if total < 35 or issues_count >= 3:
        risk_level = "CRITICAL"
    elif total < 55 or issues_count >= 2:
        risk_level = "HIGH"
    elif total < 70 or issues_count >= 1:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "symbol": f["symbol"],
        "name": f["name"],
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
        "summary": f"امتیاز کلی: {total}% - {'مناسب خرید' if rec in ('STRONG_BUY', 'BUY') else 'قابل توجه' if rec == 'WATCHLIST' else 'نیازمند بررسی'} ({issues_count} مشکل شناسایی شده)",
    }
