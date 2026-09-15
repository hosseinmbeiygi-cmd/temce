"""FundChatExplainer — لایه تفسیر فارسی روی خروجی FundScoringEngine.

این ماژول هرگز امتیاز «اختراع» نمی‌کند؛ فقط بر اساس JSON قطعی موتور
امیتازدهی، متن گفت‌وگوی فارسی و کارت داده‌ای تولید می‌کند.

اگر در آینده LLM API اضافه شد، فقط `explain_with_llm()` را با adapter
جایگزین کنید — بقیه معماری تغییر نمی‌کند.
"""

from __future__ import annotations

from typing import Any

from core.logging import get_logger
from services.fund_scoring import FundScoreResult

logger = get_logger(__name__)


# ── پرامپت سیستمی (برای استفاده در آینده با LLM) ─────────────────────────────

FUND_EXPLAINER_SYSTEM_PROMPT = """شما «دستیار ارشد تحلیل صندوق‌های سرمایه‌گذاری» در یک پلتفرم تحلیلی ایرانی هستید.
شما لایه هوش تحلیلی (LLM Layer) کنار یک Scoring Engine کوانت هستید.

# منابع داده رسمی (فقط بر این مبنا تحلیل کن)
- فیپیران: NAV رسمی و عملکرد تاریخی صندوق‌ها
- TSETMC: قیمت، حجم، ترکیب مشتریان حقیقی/حقوقی
- کدال: صورت‌های مالی و اطلاعیه‌های نهادهای سرمایه‌گذاری
- بورس کالا و بانک مرکزی: متغیرهای کلان (طلا، ارز، تورم، نرخ بهره بین‌بانکی)

از حافظه یا داده غایب استفاده نکن؛ اگر داده‌ای در JSON ورودی نبود، صراحتاً اعلام کن «داده در دسترس نیست».

# قوانین سیگنال‌دهی (غیرقابل نقض)
- امتیاز ۰-۱۰۰ ← یکی از ۵ سطح: «خرید قوی / خرید / نگهداری / احتیاط / اجتناب»
- Override: حباب P/NAV > +۳٪ ← سقف سیگنال «اجتناب از خرید»
- Override: حباب < -۲٪ ← کاندید ورود (در صورت سالم بودن سایر ابعاد)
- Override: news_risk=HIGH ← هشدار ریسک اجباری
- Override: spread > ۱٪ ← جریمه اجباری امتیاز نقدشوندگی
- در صورت اهرم یا Liquidity Spiral بالا، هرگز «خرید قوی» صادر نکن.

# قالب خروجی استاندارد (JSON + متن فارسی)
{
  "fund": "...", "fund_type": "...", "score": 0-100, "signal": "...",
  "reason_vector": ["۳ تا ۵ دلیل شفاف به فارسی"],
  "bubble": {"p_nav": "...", "group_avg": "...", "status": "..."},
  "risks": ["هشدارها: اهرم، ابطال، اسپرد، خبر"],
  "invalidation": "چه شرایطی سیگنال را ابطال می‌کند",
  "disclaimer": "این تحلیل توصیه سرمایه‌گذاری نیست"
}

# قوانین رفتاری
- هر دلیل در reason_vector باید به یک شاخص مشخص و مقدار عددی آن اشاره کند.
- سؤال کاربر مبهم بود ← اول نوع صندوق، افق سرمایه‌گذاری و ریسک‌پذیری او را بپرس.
- هرگز «تضمین سود»، پیش‌بینی قطعی قیمت یا توصیه شخصی صادر نکن.
"""


# ── برچسب فارسی گروه‌ها ────────────────────────────────────────────────────

GROUP_LABEL = {
    "leveraged": "اهرمی",
    "gold": "طلا و کالا",
    "fixed_income": "درآمد ثابت",
    "equity": "سهامی",
    "mixed": "مختلط",
    "sector": "بخشی",
    "index": "شاخصی",
}

LAYER_LABEL = {
    "p_nav": "حباب P/NAV",
    "liquidity_spiral": "Liquidity Spiral",
    "drawdown": "Drawdown",
    "beta_hidden_lev": "اهرم پنهان",
    "tenure": "سابقه مدیریت",
    "ter_turnover": "هزینه و گردش",
    "turnover_ter": "گردش و هزینه",
    "ter": "کارمزد",
    "fx_beta": "بتای ارز",
    "gold_corr": "همبستگی طلا",
    "spread_liquidity": "اسپرد و نقدشوندگی",
    "nav_stability": "ثبات NAV",
    "rate_beta": "بتای نرخ بهره",
    "issuer_credit": "اعتبار نهاد",
    "alpha_ir": "آلفا / IR",
    "capture": "Capture Ratios",
    "style_drift": "انحراف سبک",
    "behavior_persistence": "پایداری عملکرد",
    "behavior_gap": "شکاف رفتاری",
    "tracking_diff": "Tracking Difference",
    "news_risk": "ریسک خبری",
}


# ── تابع اصلی توضیح فارسی ──────────────────────────────────────────────────


def _format_overrides(overrides: list[str]) -> str:
    if not overrides:
        return ""
    items = "\n".join(f"  • {o}" for o in overrides)
    return f"\n\n⚙️ **قوانین شرطی اعمال‌شده:**\n{items}"


def _format_risks(risks: list[str]) -> str:
    if not risks:
        return ""
    items = "\n".join(f"  ⚠ {r}" for r in risks)
    return f"\n\n🚨 **هشدارها:**\n{items}"


def _format_bubble(bubble: dict[str, Any]) -> str:
    pnav = bubble.get("p_nav", "—")
    grp = bubble.get("group_avg", "—")
    status = bubble.get("status", "balanced")
    status_fa = {
        "high_bubble": "🔴 حباب بالا (احتیاط)",
        "discounted": "🟢 تخفیف (کاندید ورود)",
        "balanced": "🟡 متعادل",
    }.get(status, status)
    return f"P/NAV: {pnav} | میانگین گروه: {grp} | وضعیت: {status_fa}"


def _format_top_layers(layers: dict[str, float], n: int = 2) -> tuple[str, str]:
    if not layers:
        return "", ""
    sorted_layers = sorted(layers.items(), key=lambda kv: kv[1], reverse=True)
    top = sorted_layers[:n]
    bottom = sorted_layers[-n:]

    def line(items):
        return "\n".join(f"  • {LAYER_LABEL.get(k, k)}: {v:.0f}/۱۰۰" for k, v in items)

    return (
        f"\n\n💪 **نقاط قوت:**\n{line(top)}",
        f"\n\n📉 **نقاط ضعف:**\n{line(bottom)}",
    )


def explain_fund(result: FundScoreResult) -> dict[str, Any]:
    """تبدیل خروجی کوانت به پاسخ گفت‌وگویی فارسی.

    خروجی شامل:
    - text: متن گفت‌وگویی
    - data: JSON ساختاریافته (برای اتصال به UI/Alert/Telegram)
    - suggestions: پیشنهادهای بعدی
    """
    grp = GROUP_LABEL.get(result.fund_type, result.fund_type)

    header = f"📊 **تحلیل {result.symbol} ({grp})**\n"
    headline = (
        f"**سیگنال: {result.signal_label}** · امتیاز: {result.score:.0f}/۱۰۰ · "
        f"اطمینان: {'🟢' if result.confidence == 'HIGH' else '🟡' if result.confidence == 'MEDIUM' else '🔴'} {result.confidence}"
    )

    bubble_text = _format_bubble(result.bubble)
    top, bottom = _format_top_layers(result.layer_scores, n=2)
    overrides_text = _format_overrides(result.overrides)
    risks_text = _format_risks(result.risks)

    # Reason Vector فارسی — ۳ تا ۵ دلیل (از موتور، نه اختراع)
    reason_lines = "\n".join(f"  {i + 1}. {r}" for i, r in enumerate(result.reasons[:5]))
    reasons_block = f"\n\n🧠 **بردار دلایل (Reason Vector):**\n{reason_lines}" if result.reasons else ""

    invalidation = f"\n\n❌ **ابطال سیگنال:** {result.invalidation}"

    body = "\n".join(
        x
        for x in [
            header,
            headline,
            bubble_text,
            top,
            bottom,
            reasons_block,
            overrides_text,
            risks_text,
            invalidation,
            "",
            result.disclaimer,
        ]
        if x is not None
    )

    # پیشنهادها بر اساس سیگنال
    suggestions: list[str] = []
    if result.signal in ("AVOID", "REDUCE"):
        suggestions.extend([f"مقایسه {result.symbol} با هم‌گروه", "بهترین صندوق طلای امروز", "صندوق‌های سهامی برتر"])
    elif result.signal in ("STRONG_BUY", "BUY"):
        suggestions.extend([f"اخبار {result.symbol}", f"پیش‌بینی {result.symbol}", "صندوق‌های مشابه برای مقایسه"])
    else:
        suggestions.extend([f"تحلیل {result.symbol}", "مانیتور حباب", "آربیتراژ صندوق‌ها"])
    suggestions.append("نمایش در داشبورد")

    return {
        "text": body,
        "data": result.to_dict(),
        "suggestions": suggestions,
        "type": "fund_analysis",
    }


def explain_compare_funds(results: list[FundScoreResult]) -> dict[str, Any]:
    """مقایسه تفاوت‌های شاخص‌محور چند صندوق (پرامپت: «بین دو صندوق مقایسه‌ای»)."""
    if len(results) < 2:
        return {"text": "برای مقایسه حداقل دو صندوق لازم است.", "type": "error"}

    rows = []
    for r in results:
        grp = GROUP_LABEL.get(r.fund_type, r.fund_type)
        rows.append(f"  • **{r.symbol}** ({grp}): {r.signal_label} · {r.score:.0f}/۱۰۰")

    header = "⚖️ **مقایسه شاخص‌محور صندوق‌ها:**\n" + "\n".join(rows)

    # تفاوت‌های لایه‌ای: برای هر لایه مشترک، max-min
    common_keys: set[str] = set()
    for r in results:
        common_keys |= set(r.layer_scores.keys())

    diffs: list[str] = []
    for k in sorted(common_keys):
        vals = [(r.symbol, r.layer_scores.get(k, 0.0)) for r in results]
        spread = max(v for _, v in vals) - min(v for _, v in vals)
        if spread >= 15:  # فقط تفاوت‌های معنادار
            best = max(vals, key=lambda x: x[1])
            worst = min(vals, key=lambda x: x[1])
            diffs.append(
                f"  • {LAYER_LABEL.get(k, k)}: {best[0]}={best[1]:.0f} vs {worst[0]}={worst[1]:.0f} (Δ{spread:.0f})"
            )

    diff_block = "\n\n📊 **تفاوت‌های کلیدی (Δ ≥ ۱۵):**\n" + "\n".join(diffs) if diffs else ""

    # حباب مقایسه‌ای
    bubbles = [(r.symbol, r.bubble.get("p_nav", "—")) for r in results]
    bubble_block = "\n\n💰 **حباب P/NAV:**\n" + "\n".join(f"  • {s}: {b}" for s, b in bubbles)

    return {
        "text": header + diff_block + bubble_block,
        "data": {
            "comparison": [r.to_dict() for r in results],
        },
        "suggestions": ["نمایش در صفحه مقایسه", "صندوق‌های تخفیف‌دار", "بهترین امتیاز هفتگی"],
        "type": "fund_comparison",
    }


def explain_bubble_monitor(arbitrage: list[dict[str, Any]], top_bubbles: list[dict[str, Any]]) -> dict[str, Any]:
    """توضیح فارسی برای داشبورد حباب و آربیتراژ (پرامپت: «حباب گروهی»)."""
    parts: list[str] = ["🌡️ **مانیتور حباب و آربیتراژ**"]

    if top_bubbles:
        parts.append("\n🔴 **بالاترین حباب‌ها:**")
        for b in top_bubbles[:5]:
            parts.append(f"  • {b.get('symbol', '?')}: {b.get('bubble', '?')}")

    if arbitrage:
        parts.append("\n💱 **فرصت‌های آربیتراژ (اسپرد > ۱.۵٪):**")
        for a in arbitrage[:5]:
            spread = a.get("spread", 0)
            rich = a.get("rich", {}).get("symbol", "?")
            cheap = a.get("cheap", {}).get("symbol", "?")
            parts.append(f"  • گروه {a.get('group', '?')}: {rich} (گران) ↔ {cheap} (ارزان) — اسپرد {spread:.1f}٪")

    if not top_bubbles and not arbitrage:
        parts.append("\n✅ فعلاً اسپرد معنادار یا حباب بحرانی پیدا نشد.")

    return {
        "text": "\n".join(parts),
        "data": {"top_bubbles": top_bubbles, "arbitrage": arbitrage},
        "suggestions": ["صندوق‌های تخفیف‌دار", "صندوق‌های حباب‌دار", "نمایش هیت‌مپ"],
        "type": "bubble_monitor",
    }
