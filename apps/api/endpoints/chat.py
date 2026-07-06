from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.dependencies import get_market_service, get_brsapi_query_service
from core.logging import get_logger
from schemas.common.responses import ApiResponse
from services.market_service import MarketService

logger = get_logger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    text: str
    suggestions: list[str] = []
    link: str | None = None
    link_label: str | None = None
    data: dict[str, Any] | None = None


# ── Knowledge base ────────────────────────────────────────────────

FEATURES: list[dict[str, Any]] = [
    {"keywords": ["معامله", "trade", "آخرین معامله"], "feature": "trades", "label": "تاریخچه معاملات", "link": "/trades"},
    {"keywords": ["سیگنال", "signal", "پیشنهاد"], "feature": "signals", "label": "سیگنال‌های معاملاتی", "link": "/signals"},
    {"keywords": ["توصیه", "recommendation", "خرید", "بفروش"], "feature": "recommendations", "label": "توصیه‌ها", "link": "/recommendations"},
    {"keywords": ["اخبار", "news", "خبر"], "feature": "news", "label": "اخبار بازار", "link": "/news"},
    {"keywords": ["تحلیل", "analysis", "تکنیکال", "fundamental"], "feature": "analysis", "label": "تحلیل بازار", "link": "/analysis"},
    {"keywords": ["ریسک", "risk", "var", "شاخص ریسک"], "feature": "risk", "label": "مدیریت ریسک", "link": "/risk"},
    {"keywords": ["smart", "money", "هوشمند", "پول هوشمند"], "feature": "smart_money", "label": "پول هوشمند", "link": "/smart-money"},
    {"keywords": ["screener", "غربال", "screening"], "feature": "screener", "label": "غربال‌گر هوشمند", "link": "/screener"},
    {"keywords": ["دستیار", "assistant", "چت", "chat", "سوال", "تحلیل کن"], "feature": "stock_assistant", "label": "دستیار هوشمند سهام", "link": "/assistant"},
    {"keywords": ["portfel", "portfolio", "پرتفوی", "سبد"], "feature": "portfolio", "label": "پرتفوی", "link": "/portfolio"},
    {"keywords": ["پیش‌بینی", "predict", "forecast", "ml"], "feature": "ml", "label": "پیش‌بینی هوش مصنوعی", "link": "/ml"},
    {"keywords": ["macro", "ماکرو", "اقتصاد", "تورم", "gdp"], "feature": "macro", "label": "داده‌های کلان", "link": "/macro"},
    {"keywords": ["طلا", "gold", "سکه", "ارز", "دلار"], "feature": "gold", "label": "طلا و ارز", "link": "/macro"},
    {"keywords": ["کالا", "commodity", "نفت", "مس"], "feature": "commodities", "label": "کامودیتی‌ها", "link": "/commodities"},
    {"keywords": ["رمز", "crypto", "بیت‌کوین", "bitcoin"], "feature": "crypto", "label": "ارز دیجیتال", "link": "/crypto"},
    {"keywords": ["گزارش", "report", "بازار"], "feature": "reports", "label": "گزارش‌ها", "link": "/reports"},
    {"keywords": ["آپشن", "option", "اختیار"], "feature": "options", "label": "بازار آپشن", "link": "/options"},
    {"keywords": ["صندوق", "fund", "sandoogh"], "feature": "funds", "label": "صندوق‌ها", "link": "/funds"},
    {"keywords": ["آلفا", "alpha", "استراتژی"], "feature": "alpha", "label": "استراتژی‌های آلفا", "link": "/alpha"},
    {"keywords": ["ناهنجاری", "anomaly", "anomal"], "feature": "anomalies", "label": "تشخیص ناهنجاری", "link": "/anomalies"},
    {"keywords": ["کدال", "codal", "اطلاعیه"], "feature": "codal", "label": "اطلاعیه‌های کدال", "link": "/codal"},
    {"keywords": ["نمودار", "chart", "تاریخچه", "history"], "feature": "history", "label": "تاریخچه قیمت", "link": "/brsapi/history"},
    {"keywords": ["اندیکاتور", "indicator", "rsi", "macd", "sma"], "feature": "indicators", "label": "اندیکاتورها", "link": "/indicators"},
    {"keywords": ["سلام", "hi", "hello", "درود", "شروع"], "feature": "greeting", "label": "", "link": ""},
    {"keywords": ["help", "راهنما", "کمک", "چیست", "what"], "feature": "help", "label": "", "link": ""},
]

KNOWN_SYMBOLS = [
    "فولاد", "فملی", "شپنا", "وبملت", "خودرو", "کگل", "شتران",
    "وغدیر", "تاپیکو", "کچاد", "پترول", "مس", "پارس", "حفاری",
    "شبندر", "بوعلی", "شاراک", "دکوثر", "رمپنا", "خساپا",
]


def _extract_symbol(text: str) -> str | None:
    for sym in KNOWN_SYMBOLS:
        if sym in text:
            return sym
    return None


def _build_greeting() -> ChatResponse:
    return ChatResponse(
        text="سلام! 🤖 من دستیار هوشمند بازار سرمایه هستم. می‌توانم در این موارد به شما کمک کنم:\n\n"
             "📊 **اطلاعات نمادها** — قیمت، تغییرات، تحلیل نمادهای بورسی\n"
             "📈 **تحلیل بازار** — روندها، شاخص‌ها، احساسات بازار\n"
             "🔍 **غربال‌گری** — یافتن بهترین نمادها با ۵ فاز Smart Money\n"
             "🤖 **دستیار هوشمند** — تحلیل، مقایسه و فیلتر پیشرفته سهام\n"
             "🧠 **یادگیری ماشین** — پیش‌بینی قیمت با مدل‌های AI\n"
             "🏦 **صندوق‌ها** — اطلاعات NAV و عملکرد صندوق‌ها\n"
             "📰 **اخبار** — آخرین اخبار و تحلیل احساسات\n"
             "📊 **نمودارها** — اندیکاتورهای تکنیکال و تاریخچه قیمت\n\n"
             "یک سوال بپرسید یا روی یکی از پیشنهادات زیر کلیک کنید! 👇",
        suggestions=[
            "قیمت فولاد چقدره؟",
            "بهترین نمادها کدامند؟",
            "تحلیل بازار امروز چطوره؟",
            "دستیار سهام",
            "پیش‌بینی قیمت سهم",
            "ناهنجاری‌های بازار",
        ],
    )


def _build_help() -> ChatResponse:
    return ChatResponse(
        text="🤖 **راهنمای دستیار هوشمند**\n\n"
             "می‌توانید سوالات زیر را بپرسید:\n\n"
             "🔹 **قیمت نمادها**: «قیمت فلان نماد چقدره؟»، «وضعیت فولاد»\n"
             "🔹 **بهترین نمادها**: «بهترین سهم‌ها کدامند؟»، «غربال‌گری کن»\n"
             "🔹 **تحلیل بازار**: «تحلیل بازار چطوره؟»، «احساسات بازار»\n"
             "🔹 **صندوق‌ها**: «صندوق‌ها رو ببین»، «NAV صندوق‌ها»\n"
             "🔹 **پیش‌بینی**: «پیش‌بینی قیمت سهم»، «مدل ML رو فعال کن»\n"
             "🔹 **اخبار**: «آخرین اخبار بازار»، «اخبار فولاد»\n"
             "🔹 **ناهنجاری**: «ناهنجاری‌های قیمت»، «حجم غیرعادی»\n"
             "🔹 **ریسک**: «شاخص‌های ریسک»، «مدیریت ریسک»\n\n"
             "همچنین می‌توانید نام یک نماد را بگویید تا به صفحه آن هدایت شوید.",
        suggestions=[
            "قیمت فولاد چقدره؟",
            "بهترین نمادها کدامند؟",
            "تحلیل بازار امروز",
            "ناهنجاری‌های بازار",
            "صندوق‌ها رو نشون بده",
            "help",
        ],
    )


async def _fetch_market_overview(service: MarketService) -> str:
    try:
        overview = await service.get_overview()
        if overview.success and overview.value:
            d = overview.value
            total = d.get("total_instruments", 0)
            gainers = d.get("gainers", 0)
            losers = d.get("losers", 0)
            avg_change = d.get("avg_change_pct", 0)
            value = d.get("total_value", 0)

            return (
                f"📊 **خلاصه بازار**\n\n"
                f"تعداد نمادها: {total:,}\n"
                f"مثبت: {gainers:,}\n"
                f"منفی: {losers:,}\n"
                f"میانگین تغییر: {avg_change:+.2f}%\n"
                f"ارزش کل معاملات: {value:,.0f} ریال\n"
            )
    except Exception:
        pass

    return "📊 **خلاصه بازار**\nداده‌ای برای نمایش موجود نیست."


async def _fetch_symbol_info(symbol: str, brsapi: Any) -> str:
    try:
        snap = await brsapi.get_symbol_snapshot(symbol)
        if snap:
            price = snap.get("price_last", 0)
            change = snap.get("price_last_change_pct", 0)
            volume = snap.get("trade_volume", 0)
            value = snap.get("trade_value", 0)

            return (
                f"📈 **{symbol}**\n\n"
                f"قیمت آخر: {price:,.0f} ریال\n"
                f"تغییرات: {change:+.2f}%\n"
                f"حجم معاملات: {volume:,}\n"
                f"ارزش معاملات: {value:,.0f} ریال\n"
            )
    except Exception:
        pass

    return f"🔍 **{symbol}**\nداده‌ای برای این نماد یافت نشد."


async def _fetch_top_movers(brsapi: Any) -> str:
    try:
        snapshots = await brsapi.get_latest_snapshots(limit=20)
        if snapshots:
            sorted_snaps = sorted(snapshots, key=lambda s: abs(s.get("price_last_change_pct", 0) or 0), reverse=True)
            top = sorted_snaps[:5]

            lines = ["🔥 **پرمتحرک‌ترین نمادها**\n"]
            for s in top:
                sym = s.get("symbol", "")
                chg = s.get("price_last_change_pct", 0) or 0
                arrow = "🟢" if chg > 0 else "🔴"
                lines.append(f"{arrow} {sym}: {chg:+.2f}%")
            return "\n".join(lines)
    except Exception:
        pass

    return "داده‌ای برای نمایش موجود نیست."


@router.post("", summary="AI Chatbot", description="Ask questions about the capital market")
async def chat(
    body: ChatRequest,
    market_service: MarketService = Depends(get_market_service),
    brsapi=Depends(get_brsapi_query_service),
) -> ApiResponse[ChatResponse]:
    try:
        msg = body.message.strip()
        if not msg:
            return ApiResponse[ChatResponse](success=True, data=_build_greeting())

        msg_lower = msg.lower()

        # ── Intent detection ──
        symbol = _extract_symbol(msg)

        # Greeting
        if any(k in msg_lower for k in ["سلام", "hi", "hello", "درود", "شروع", "/start"]):
            return ApiResponse[ChatResponse](success=True, data=_build_greeting())

        # Help
        if any(k in msg_lower for k in ["help", "راهنما", "کمک", "چیست", "توانی", "what can"]):
            return ApiResponse[ChatResponse](success=True, data=_build_help())

        # Market overview
        if any(k in msg_lower for k in ["بازار", "market", "today", "امروز", "خلاصه", "overview"]):
            text = await _fetch_market_overview(market_service)
            top_text = await _fetch_top_movers(brsapi)
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text=f"{text}\n\n{top_text}",
                    suggestions=["قیمت فولاد", "بهترین نمادها", "ناهنجاری‌ها", "تحلیل تکنیکال"],
                    link="/markets",
                    link_label="📊 بازار",
                ),
            )

        # Best stocks / screener
        if any(k in msg_lower for k in ["بهترین", "best", "برتر", "screener", "غربال", "پیشنهاد سهم"]):
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text="🔍 **غربال‌گر هوشمند Smart Money**\n\n"
                         "برای مشاهده بهترین نمادها بر اساس ۵ فاز تحلیل:\n"
                         "1️⃣ نقدشوندگی\n"
                         "2️⃣ قدرت خرید\n"
                         "3️⃣ ساختار قیمت\n"
                         "4️⃣ جریان سفارش\n"
                         "5️⃣ آمادگی شکست\n\n"
                         "می‌توانید فیلترهای مختلف را در صفحه غربال‌گر اعمال کنید.",
                    suggestions=["Screener با SMC بالا", "نمادهای با نقدشوندگی قوی", "تحلیل بازار"],
                    link="/screener",
                    link_label="🔍 غربال‌گر",
                ),
            )

        # Stock assistant
        if any(k in msg_lower for k in ["دستیار", "assistant", "چت", "chat", "تحلیل کن", "مقایسه", "فیلتر"]):
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text="🤖 **دستیار هوشمند سهام**\n\n"
                         "برای استفاده از دستیار هوشمند:\n"
                         "• «تحلیل فولاد» — تحلیل کامل یک نماد\n"
                         "• «مقایسه فولاد و خودرو» — مقایسه دو سهم\n"
                         "• «فیلتر RSI<30 ROE>20» — فیلتر پیشرفته\n"
                         "• «سهام ارزنده» — سهام با P/E پایین\n\n"
                         "می‌توانید مستقیماً پیام خود را ارسال کنید.",
                    suggestions=["تحلیل فولاد", "مقایسه فولاد و خودرو", "سهام ارزنده", "فیلتر P/E<8"],
                    link="/assistant",
                    link_label="🤖 دستیار سهام",
                ),
            )

        # Symbol info
        if symbol:
            info = await _fetch_symbol_info(symbol, brsapi)
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text=info,
                    suggestions=[
                        f"نمودار {symbol}",
                        f"اخبار {symbol}",
                        f"تحلیل {symbol}",
                        "خلاصه بازار",
                    ],
                    link=f"/symbol/{symbol}",
                    link_label=f"📈 {symbol}",
                ),
            )

        # Anomalies
        if any(k in msg_lower for k in ["ناهنجاری", "anomal", "غیرعادی", "spike", "جهش"]):
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text="🚨 **تشخیص ناهنجاری بازار**\n\n"
                         "ناهنجاری‌های قیمت و حجم با تحلیل Z-Score شناسایی می‌شوند.\n"
                         "آستانه پیش‌فرض: ۲.۵σ برای قیمت، ۲.۰σ برای حجم.\n"
                         "نتایج به تفکیک شدت (شدید/متوسط/ضعیف) نمایش داده می‌شوند.",
                    suggestions=["ناهنجاری‌های شدید", "ناهنجاری حجم", "قیمت فولاد"],
                    link="/anomalies",
                    link_label="🚨 ناهنجاری‌ها",
                ),
            )

        # Risk
        if any(k in msg_lower for k in ["ریسک", "risk", "var", "شاخص ریسک", "مدیریت ریسک"]):
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text="⚠️ **مدیریت ریسک**\n\n"
                         "شاخص‌های ریسک قابل پایش:\n"
                         "• VaR (۹۵%)\n"
                         "• CVaR\n"
                         "• Sharpe Ratio\n"
                         "• Beta\n"
                         "• Max Drawdown\n"
                         "• Volatility\n"
                         "• Exposure\n"
                         "• Concentration",
                    suggestions=["شاخص‌های ریسک", "ناهنجاری‌ها", "بهترین نمادها"],
                    link="/risk",
                    link_label="⚠️ ریسک",
                ),
            )

        # Funds
        if any(k in msg_lower for k in ["صندوق", "fund", "sandoogh", "nav"]):
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text="🏦 **صندوق‌های سرمایه‌گذاری**\n\n"
                         "اطلاعات کاملی از صندوق‌ها موجود است:\n"
                         "• NAV و تغییرات روزانه\n"
                         "• اسپارکلاین ۳۰ روزه\n"
                         "• نوع صندوق (کالایی/سهامی/درآمد ثابت/مختلط)\n"
                         "• ارزش بازار، حجم معاملات\n"
                         "• جریان پول حقیقی/حقوقی",
                    suggestions=["صندوق‌های کالایی", "بهترین صندوق‌ها", "خلاصه بازار"],
                    link="/funds",
                    link_label="🏦 صندوق‌ها",
                ),
            )

        # ML / Prediction
        if any(k in msg_lower for k in ["پیش‌بینی", "predict", "ml", "مدل", "یادگیری ماشین"]):
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text="🧠 **یادگیری ماشین و پیش‌بینی**\n\n"
                         "مدل‌های فعال:\n"
                         "• **Linear Regression** — رگرسیون خطی\n"
                         "• **Random Forest** — جنگل تصادفی\n"
                         "• **XGBoost** — گرادیان boosting\n"
                         "• **Logistic Regression** — رگرسیون لجستیک\n\n"
                         "می‌توانید یک نماد را انتخاب کرده و پیش‌بینی قیمت دریافت کنید.",
                    suggestions=["پیش‌بینی فولاد", "مشاهده مدل‌ها", "آموزش مدل جدید"],
                    link="/ml",
                    link_label="🧠 پیش‌بینی AI",
                ),
            )

        # Default: general response with feature suggestion
        features_found = []
        for feat in FEATURES:
            if any(k in msg_lower for k in feat["keywords"]):
                features_found.append(feat)

        if features_found:
            feat = features_found[0]
            return ApiResponse[ChatResponse](
                success=True,
                data=ChatResponse(
                    text=f"🔍 به بخش **{feat['label']}** هدایت می‌شوید.\n\n"
                         f"برای اطلاعات بیشتر، روی لینک زیر کلیک کنید یا سوال دقیق‌تری بپرسید.",
                    suggestions=[
                        "خلاصه بازار",
                        "بهترین نمادها",
                        "قیمت فولاد",
                        "ناهنجاری‌ها",
                    ],
                    link=feat.get("link"),
                    link_label=feat.get("label"),
                ),
            )

        # Fallback
        return ApiResponse[ChatResponse](
            success=True,
            data=ChatResponse(
                text="🤖 **سوال شما را متوجه نشدم.**\n\n"
                     "لطفاً یکی از گزینه‌های زیر را انتخاب کنید یا سوال خود را واضح‌تر بپرسید:\n\n"
                     "• «قیمت فولاد چقدره؟»\n"
                     "• «بهترین نمادها کدامند؟»\n"
                     "• «تحلیل بازار امروز»\n"
                     "• «صندوق‌ها رو ببین»\n"
                     "• «پیش‌بینی قیمت»\n"
                     "• «help» برای راهنما",
                suggestions=[
                    "قیمت فولاد چقدره؟",
                    "بهترین نمادها کدامند؟",
                    "تحلیل بازار امروز",
                    "صندوق‌ها رو ببین",
                    "پیش‌بینی قیمت",
                    "ناهنجاری‌های بازار",
                ],
            ),
        )
    except Exception as exc:
        logger.exception("Chat error")
        return ApiResponse[ChatResponse](
            success=False,
            data=ChatResponse(text="⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید."),
        )
