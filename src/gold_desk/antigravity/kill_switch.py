"""Kill-Switch و Sentiment — تحلیل رویدادهای بحرانی.

مطابق spec: 5 منبع خبری + 3 دسته کلیدواژه + 3 قانون circuit-breaker
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ── منابع خبری ────────────────────────────────────────────────────
NEWS_SOURCES: list[str] = [
    "cbi.ir",
    "tsetmc.ir/News",
    "ime.co.ir/News",
    "tasnimnews.com",
    "isna.ir",
]

# ── کلمات کلیدی ماشه ─────────────────────────────────────────────
TRIGGER_KEYWORDS: dict[str, list[str]] = {
    "war_conflict": ["جنگ", "حمله", "تنش نظامی", "پاسخ نظامی", "شورای امنیت"],
    "sanctions_shock": ["تحریم جدید", "مسدودسازی", "لیست سیاه", "FATF"],
    "monetary_shock": ["تغییر نرخ ارز رسمی", "سیاست ارزی جدید", "حراج شمش", "عرضه سکه"],
}

# ── قوانین Kill-Switch ──────────────────────────────────────────
KILL_SWITCH_RULES: dict[str, str] = {
    "volatility_circuit_breaker": "نوسان قیمت اونس یا دلار آزاد > 5% در بازه کمتر از 2 ساعت",
    "futures_margin_shock": "افزایش ناگهانی وجه تضمین اولیه توسط بورس کالا",
    "systemic_freeze": "توقف نمادهای طلا در بورس یا تعطیلی بازار طلا",
}

EMERGENCY_ACTION: dict[str, str] = {
    "status": "KILL_SWITCH_ACTIVE",
    "directive": "لغو تمامی سفارش‌های در صف، خروج از موقعیت‌های اهرمی آتی (IME)، حفظ موقعیت‌های ETF بدون اهرم.",
}


@dataclass(frozen=True)
class KillSwitchStatus:
    status: Literal["NORMAL", "WARNING", "ACTIVE"]
    directive: str | None
    triggered_rules: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    reason: str | None = None


def _contains_keyword(text: str, keywords: list[str]) -> list[str]:
    found: list[str] = []
    for kw in keywords:
        if kw in text:
            found.append(kw)
    return found


def scan_news_for_triggers(news_texts: list[str]) -> dict[str, list[str]]:
    """اسکن متن اخبار برای کلمات ماشه."""
    hits: dict[str, list[str]] = {}
    combined = " ".join(news_texts)
    for category, kws in TRIGGER_KEYWORDS.items():
        matched = _contains_keyword(combined, kws)
        if matched:
            hits[category] = matched
    return hits


def evaluate_kill_switch(
    *,
    ounce_change_2h_pct: float | None = None,
    usd_change_2h_pct: float | None = None,
    margin_increased: bool = False,
    market_frozen: bool = False,
    news_texts: list[str] | None = None,
) -> KillSwitchStatus:
    """ارزیابی وضعیت Kill-Switch.

    اولویت: ACTIVE > WARNING > NORMAL
    """
    triggered: list[str] = []
    matched: list[str] = []

    # 1. Volatility circuit breaker
    if ounce_change_2h_pct is not None and abs(ounce_change_2h_pct) > 5:
        triggered.append("volatility_circuit_breaker")
    if usd_change_2h_pct is not None and abs(usd_change_2h_pct) > 5:
        if "volatility_circuit_breaker" not in triggered:
            triggered.append("volatility_circuit_breaker")

    # 2. Margin shock
    if margin_increased:
        triggered.append("futures_margin_shock")

    # 3. Systemic freeze
    if market_frozen:
        triggered.append("systemic_freeze")

    # 4. Keyword scan
    if news_texts:
        hits = scan_news_for_triggers(news_texts)
        for cat, kws in hits.items():
            matched.extend(kws)
            # war/sanctions => WARNING at least
            if cat in ("war_conflict", "sanctions_shock") and not triggered:
                # don't auto-ACTIVE on keywords alone, but WARNING
                pass

    # تصمیم نهایی
    if triggered:
        return KillSwitchStatus(
            status="ACTIVE",
            directive=EMERGENCY_ACTION["directive"],
            triggered_rules=triggered,
            matched_keywords=matched,
            reason=f"قوانین فعال: {', '.join(triggered)}",
        )
    if matched:
        # keywords بدون circuit-breaker => WARNING
        return KillSwitchStatus(
            status="WARNING",
            directive="کاهش اهرم، عدم ورود جدید، رصد لحظه‌ای اخبار",
            triggered_rules=[],
            matched_keywords=matched,
            reason=f"کلمات ماشه شناسایی شد: {', '.join(matched)}",
        )
    return KillSwitchStatus(
        status="NORMAL",
        directive=None,
        triggered_rules=[],
        matched_keywords=[],
        reason="شرایط عادی",
    )


# ── سازگاری با hard_stops موجود ──────────────────────────────────
def map_to_hard_stop(kill_status: KillSwitchStatus) -> dict:
    """نگاشت به فرمت hard_stops فعلی برای scorer."""
    return {
        "active": kill_status.status == "ACTIVE",
        "reason": kill_status.reason,
    }
