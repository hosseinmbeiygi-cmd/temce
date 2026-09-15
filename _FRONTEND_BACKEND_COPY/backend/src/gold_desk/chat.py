"""GoldDesk Chatbot — تحلیل interactive با LLM.

از ChatEngine موجود temce استفاده می‌کنه، اما با system prompt غنی شامل:
- snapshot فعلی (score, refs, coins, funds)
- DCA plan
- portfolio P&L
- pattern detection

پیام‌ها فارسی هستند و لحن شخصی + مالی دارند.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_system_prompt(snapshot: dict | None, portfolio: dict | None, patterns: dict | None) -> str:
    """ساخت system prompt با context کامل بازار + portfolio کاربر."""
    parts: list[str] = [
        "تو یک دستیار تحلیلگر بازار طلای ایران هستی به نام GoldDesk.",
        "پاسخ‌هایت کوتاه، دقیق، و بر اساس داده‌های لحظه‌ای بازار است.",
        "به فارسی پاسخ بده. لحن محترمانه ولی صمیمی.",
        "از اصطلاحات تخصصی استفاده کن ولی توضیح کوتاه بده.",
        "هرگز توصیه مالی قطعی نده — بگو 'بر اساس داده‌ها' یا 'احتیاط'.",
        "",
    ]

    if snapshot:
        score = snapshot.get("score", {})
        refs = snapshot.get("references", {})
        coins = snapshot.get("coins", {})
        funds = snapshot.get("funds", [])

        parts.append("═══ وضعیت فعلی بازار ═══")
        parts.append(f"امتیاز کلی: {score.get('total', '?')}/100 → {score.get('decision', '?')}")
        if refs:
            parts.append(
                f"اونس جهانی: ${refs.get('xau_usd', '?'):.0f}"
                if isinstance(refs.get("xau_usd"), (int, float))
                else f"اونس: {refs.get('xau_usd', '?')}"
            )
            parts.append(
                f"دلار آزاد: {refs.get('usd_irt', '?'):,.0f} تومان"
                if isinstance(refs.get("usd_irt"), (int, float))
                else f"دلار: {refs.get('usd_irt', '?')}"
            )
            parts.append(f"شکاف درهم: {refs.get('aed_gap_pct', 0):.2f}٪")
        emami = coins.get("coin_emami", {})
        if emami:
            parts.append(f"حباب سکه امامی: {emami.get('bubble_pct', 0):.2f}٪")
        if funds:
            parts.append(f"تعداد صندوق‌های رصد شده: {len(funds)}")
        parts.append("")

    if portfolio:
        parts.append("═══ Portfolio کاربر ═══")
        parts.append(f"ارزش فعلی: {portfolio.get('total_value', 0):,.0f} تومان")
        parts.append(f"هزینه: {portfolio.get('total_cost', 0):,.0f} تومان")
        pnl = portfolio.get("total_pnl", 0)
        pct = portfolio.get("total_pnl_pct", 0)
        sign = "+" if pnl >= 0 else ""
        parts.append(f"P&L: {sign}{pnl:,.0f} تومان ({sign}{pct:.2f}٪)")
        parts.append("")

    if patterns:
        parts.append("═══ الگوهای شناسایی‌شده ═══")
        for p in patterns.get("patterns", []):
            parts.append(f"- {p.get('description', '?')} (confidence: {p.get('confidence', 0):.0%})")
        parts.append(f"توصیه: {patterns.get('recommendation', 'صبر')}")
        parts.append("")

    return "\n".join(parts)


async def ask_gold_assistant(
    question: str, snapshot: dict | None, portfolio: dict | None, patterns: dict | None
) -> str:
    """ارسال سؤال به ChatEngine با system prompt غنی."""
    try:
        from services.chat.chat_engine import ChatEngine

        system_prompt = build_system_prompt(snapshot, portfolio, patterns)
        engine = ChatEngine()

        # ترکیب system + user
        prompt = f"{system_prompt}\n\nسؤال کاربر: {question}\n\nپاسخ کوتاه و دقیق:"

        result = await engine.process(prompt, user_id="golddesk")
        if isinstance(result, dict):
            return result.get("text") or result.get("response") or "خطا در پاسخ."
        return str(result) if result else "پاسخی دریافت نشد."
    except Exception as exc:
        logger.warning("chat engine failed, fallback: %s", exc)
        return _fallback_response(question, snapshot, portfolio)


def _fallback_response(question: str, snapshot: dict | None, portfolio: dict | None) -> str:
    """پاسخ ساده بدون LLM (fallback)."""
    q = question.lower()
    if "حباب" in q or "bubble" in q:
        if snapshot:
            emami = snapshot.get("coins", {}).get("coin_emami", {})
            bpct = emami.get("bubble_pct")
            if bpct is not None:
                if bpct < 8:
                    return f"حباب سکه امامی {bpct:.1f}٪ — در محدوده امن. خرید منطقی است."
                if bpct < 22:
                    return f"حباب سکه امامی {bpct:.1f}٪ — احتیاط کنید. صبر بهتر است."
                return f"حباب سکه امامی {bpct:.1f}٪ — اشباع خرید. صبر کنید."
    if "بخر" in q or "خرید" in q:
        score = snapshot.get("score", {}).get("total", 0) if snapshot else 0
        decision = snapshot.get("score", {}).get("decision", "?") if snapshot else "?"
        return f"امتیاز فعلی {score} → {decision}. {('خرید قوی' if decision == 'GREEN' else 'صبر کنید' if decision == 'RED' else 'خرید محتاطانه')}."
    if "p&l" in q or "سود" in q or "زیان" in q:
        if portfolio:
            pnl = portfolio.get("total_pnl", 0)
            pct = portfolio.get("total_pnl_pct", 0)
            sign = "+" if pnl >= 0 else ""
            return f"P&L شما: {sign}{pnl:,.0f} تومان ({sign}{pct:.2f}٪)"
    if "dca" in q or "پله" in q:
        return "برای فعال‌سازی پله بعدی DCA، به تب Portfolio → DCA Plans بروید."
    return "سؤال شما دریافت شد. برای تحلیل دقیق، از تب‌های Dashboard یا Analytics استفاده کنید."
