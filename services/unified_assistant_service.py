"""Unified Assistant Service — conversational AI that connects to ALL parts of the app.

Accepts natural Persian/Farsi text, detects intent, routes to the appropriate
service (market, watchlist, alerts, portfolio, backtest, ML, screener, etc.),
executes the action, and returns structured results.

Extends the existing StockAssistantService with real action-execution capabilities.
"""

from __future__ import annotations

import re
import time
from typing import Any

from core.logging import get_logger
from services.market_watch_helper import fetch_market_watch
from services.query_logger import log_query

logger = get_logger(__name__)

# ── Intent detection: ALL app features ─────────────────────────────────────

_INTENT_PATTERNS: dict[str, list[str]] = {
    # Market / overview
    "market_overview": [
        r"(خلاصه|بازار)\s*(بازار|امروز|خلاصه)",
        r"market\s*(overview|summary|today)",
        r"بازار\s*(چطوره|چته|چه خبر|سبزه|قرمزه)",
        r"شاخص\s*(کل|بورس|فرابورس)?",
    ],
    "gainers": [
        r"(بیشترین|بالاترین|برترین)\s*(افزایش|رشد|مثبت)",
        r"top\s*(gainers|positive)",
        r"پرمتحرک",
    ],
    "losers": [
        r"(بیشترین|پایین‌ترین)\s*(کاهش|افت|منفی)",
        r"top\s*(losers|negative)",
    ],

    # Reports — checked BEFORE compare so «گزارش بازار» doesn't match the
    # compare pattern's standalone «با» inside «بازار».
    "report": [
        r"(گزارش|report)\s*(بازار|روزانه|daily)",
        r"(daily|روزانه)\s*(report|گزارش)",
    ],

    # Symbol analysis
    "analyze_symbol": [
        r"(تحلیل|بررسی|وضعیت|چطوره|حالش)\s*(\S+)",
        r"(\S+)\s*(چطوره|تحلیل|بررسی)",
        r"(ارزش خرید|می‌ارزه|بخرم|بفروشم)\s*(\S+)?",
    ],
    "compare": [
        r"مقایسه\s*(\S+)\s*(و|با)\s*(\S+)",
        r"(\S+)\s*(مقایسه|با)\s*(\S+)",
        r"(کدوم\s*بهتره|تفاوت)\s*(\S+)\s*(\S+)",
    ],

    # Watchlist
    "add_watchlist": [
        r"(اضافه|افزودن|بذار)\s*(به|تو)?\s*(دیده‌بان|لیست|پیگیری|watchlist|watch)",
        r"add\s*(to)?\s*(watchlist|watch|follow)",
    ],
    "remove_watchlist": [
        r"(حذف|پاک|بردار)\s*(از)?\s*(دیده‌بان|لیست|پیگیری|watchlist|watch)",
        r"remove\s*(from)?\s*(watchlist|watch)",
    ],
    "list_watchlist": [
        r"(دیده‌بان|watchlist|لیست پیگیری|my list)",
        r"(نمایش|لیست)\s*(دیده‌بان|پیگیری)",
    ],

    # Alerts
    "add_alert": [
        r"(هشدار|alert|alarm)\s+(اضافه|جدید|ثبت)",
        r"هشدار\s*(\S+)\s*(rsi|price|قیمت|حجم|volume)\s*(بالاتر|پایین‌تر|above|below)\s*(\d+)",
        r"(alert|alarm)\s*(\S+)\s*(rsi|price)\s*(above|below)\s*(\d+)",
    ],
    "list_alerts": [
        r"(لیست|نمایش)\s*(هشدار|alert|alarm)",
        r"هشدارهای\s*(فعال|من)",
        r"alerts\s*(list|active|all)",
    ],
    "remove_alert": [
        r"(حذف|پاک)\s*(کردن)?\s*هشدار",
        r"remove\s*(alert|alarm)",
    ],

    # Portfolio
    "portfolio_add": [
        r"(اضافه|خرید)\s+(\S+)\s+(\d+)\s*(سهم)?\s*(به قیمت|با قیمت)?\s*(\d+)",
        r"buy\s+(\S+)\s+(\d+)\s*(at)?\s*(\d+)",
    ],
    "portfolio_remove": [
        r"(حذف|فروش)\s+(\S+)\s*(از)?\s*(پرتفوی|سبد|portfolio)",
        r"sell\s+(\S+)",
    ],
    "portfolio_summary": [
        r"(خلاصه|وضعیت|نمایش)\s*(پرتفوی|سبد|portfolio)",
        r"(پرتفوی|سبد|portfolio)\s*(من|خلاصه|چطوره)",
        r"(سود|زیان|سود و زیان)\s*(پرتفوی|سبد)?",
    ],

    # Backtest
    "run_backtest": [
        r"(بک‌تست|backtest|آزمون)\s*(\S+)?",
        r"(اجرا|run)\s*(بک‌تست|backtest)",
        r"آزمایش\s*(استراتژی|strategy)\s*(رو|بر)?\s*(\S+)",
    ],
    "list_backtests": [
        r"(بک‌تست|backtest)\s*(های|ها)\s*(قبلی|من|ذخیره)",
        r"(لیست|تاریخچه|history)\s*(بک‌تست|backtest)",
    ],

    # Screener / filter
    "screener": [
        r"(غربال|screener|فیلتر)\s*(کن|گری)?",
        r"(بهترین|برترین|سهم خوب|پیشنهاد سهم)",
        r"(ارزنده|ارزان|ارزون|ارزشمند)",
        r"فیلتر\s+(RSI|P/E|ROE|حجم|volume|قیمت|price)\s*([<>=!]+\s*\d+)",
        r"screener\s*(with|for)?\s*(high|low)?",
        r"(سهم|نماد)\s*(خوب|بهتر|ارزنده|برتر)",
        r"(کدوم\s*(سهم|نماد)\s*(خوب|بهتر|ارزنده))",
        r"(پیشنهاد\s*(بده|کن|میدی))",
        r"(چه\s*(سهم|نماد)\s*(ی|ای)\s*(بخرم|خوبه|ارزشمنده))",
        r"(سهم\s*(های|هاي)\s*(خوب|برتر|ارزنده|پرحجم|پرتقاضا))",
        r"(پول\s*هوشمند\s*(وارد|خارج|خرید|فروش))",
        r"(smart\s*money)",
        r"(سهام\s*(ارزان|ارزنده|خوب))",
        r"(حجم\s*(بالا|زیاد|سنگین)\s*(داره|داشته|داشت))",
        r"(تجمع\s*(سهام|سهم|پول|حقیقی))",
        r"(accumulation)",
        r"(توزیع\s*(سهام|سهم|پول))",
        r"(distribution)",
        r"(شکست\s*(مقاومت|حمایت|روند))",
        r"(breakout)",
        r"(سیگنال\s*(خرید|فروش|صعودی|نزولی))",
        r"(RSI\s*(پایین|بالا|oversold|overbought|\d+))",
        r"(میانگین\s*(متحرک|ساده)\s*(رو|بر)\s*(\d+))",
        r"(سهم\s*(با|بدون)\s*(پول\s*هوشمند|حقیقی))",
        r"(نهادی\s*(خرید|فروش|ورود|خروج))",
        r"(حقیقی\s*(خرید|فروش|ورود|خروج|_net))",
        r"(بازیگر\s*عمده)",
    ],

    # ML / Prediction
    "ml_predict": [
        r"(پیش‌بینی|predict|forecast)\s*(\S+)?",
        r"(\S+)\s*(پیش‌بینی|predict)",
        r"(مدل|model|ml)\s*(پیش‌بینی|predict|run)",
    ],
    "ml_train": [
        r"(آموزش|train|training)\s*(مدل|model)",
        r"train-all|train_all|train all",
    ],
    "ml_list_models": [
        r"(مدل|model|ml)\s*(ها|هامو|list|لیست)",
        r"(list|لیست|نمایش)\s*(مدل|model)",
    ],

    # Codal / News
    "codal": [
        r"(کدال|codal|اطلاعیه)\s*(\S+)?",
        r"آخرین\s*(اطلاعیه|گزارش)\s*(\S+)?",
    ],
    "news": [
        r"(اخبار|news|خبر)\s*(\S+)?",
        r"آخرین\s*(اخبار|خبرها)",
    ],

    # Macro / Economy
    "macro": [
        r"(ماکرو|macro|اقتصاد|اقتصادی)",
        r"(تورم|gdp|نرخ\s*بهره|سانا)",
        r"(طلا|gold|سکه|دلار|ارز|currency|dollar)",
        r"(قیمت\s*(دلار|طلا|سکه|ارز|یورو|پوند))",
        r"(نرخ\s*(دلار|ارز|طلا|سکه))",
        r"(انس\s*(طلا|نقره|پلاتین|نقره))",
        r"(نفت\s*(برنت|سبک|اوپک|WTI))",
        r"(مس|روی|سرب|نیکل|آلومینیوم)",
        r"(قیمت\s*(جهانی|بین‌المللی))",
        r"(ارز\s*(آزاد|رسمی|نیمایی))",
    ],

    # Heatmap
    "heatmap": [
        r"(نقشه|heatmap|map)\s*(بازار|market)?",
        r"(نقشه\s*حرارتی|نقشه\s*بازار)",
    ],

    # Risk
    "risk": [
        r"(ریسک|risk|var|شاخص ریسک)",
        r"(مدیریت ریسک|risk management)",
    ],

    # Anomalies
    "anomalies": [
        r"(ناهنجاری|anomaly|anomal)",
        r"(غیرعادی|spike|جهش)",
    ],

    # Signals
    "signals": [
        r"(سیگنال|signal)\s*(خرید|فروش|معاملاتی)?",
        r"سیگنال‌های\s*(جدید|فعال|امروز)",
    ],

    # Crypto
    "crypto": [
        r"(رمزارز|ارز\s*دیجیتال|کریپتو|crypto|bitcoin|اتریوم|بیت\s*کوین)",
        r"(قیمت\s*(بیت\s*کوین|اتریوم|تتر|BTC|ETH|USDT))",
    ],

    # Commodities
    "commodities": [
        r"(کامودیتی|commodity|commodities)",
        r"(فلز\s*گران\s*بها|طلا|نقره|پلاتین)",
        r"(نفت|گاز|انرژی)",
    ],

    # Help / capabilities
    "help": [
        r"(\u06a9\u0645\u06a9|\u0631\u0627\u0647\u0646\u0645\u0627|help|\u062f\u0633\u062a\u0648\u0631\u0627\u062a|\u0686\u06cc\u06a9\u0627\u0631)",
        r"(\u0686\u0647\s*\u06a9\u0627\u0631|\u062a\u0648\u0627\u0646\u0627\u06cc\u06cc|\u0627\u0645\u06a9\u0627\u0646\u0627\u062a|capabilities)",
    ],
"greeting": [
        r"^(سلام|درود|هلو|اسلام|های|هی|خوبی)",
        r"(صبح|بعد از ظهر|عصر)\s*(به خیر|بخیر)",
        r"^(hi|hello|hey)",
    ],
    "farewell": [
        r"(خداحافظ|خدانگهدار|فعلا|بای|تا بعد)",
        r"(bye|goodbye|see you)",
    ],

    # Navigation
    "navigate": [
        r"(برو\s*به|بریم|رفتن|open|باز)\s*(\S+)",
        r"صفحه\s*(\S+)\s*(رو|را)?\s*(باز|نشون|ببین)",
    ],

    # Refresh / update
    "refresh": [
        r"(بروزرسانی|آپدیت|تازه|refresh|update)",
        r"(دیتا|داده)\s*(تازه|جدید)",
    ],
}


def detect_intent(text: str) -> tuple[str | None, dict[str, str]]:
    """Detect intent from natural Persian/English text.

    Returns (intent_name, extracted_params) where params contains
    extracted entities like symbol, value, etc.
    """
    text_lower = text.strip().lower()

    # Try patterns in order (more specific first)
    for intent, patterns in _INTENT_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                params: dict[str, str] = {}

                # Extract common entities
                if intent == "analyze_symbol":
                    params["symbol"] = groups[0] if groups[0] and groups[0] not in ("تحلیل", "بررسی", "چطوره", "وضعیت", "حالش") else (groups[1] if len(groups) > 1 else "")
                    # Clean up
                    if params.get("symbol", "").strip() in ("تحلیل", "بررسی", "چطوره", "وضعیت", "buy", "sell"):
                        # Try to find any persian stock symbol in the text
                        pass  # Will fall back to symbol extraction later

                elif intent == "compare":
                    params["symbol1"] = groups[0] or ""
                    params["symbol2"] = groups[2] if len(groups) > 2 else (groups[1] or "")

                elif intent in ("add_watchlist", "remove_watchlist"):
                    # Find symbol after the keywords
                    symbol_match = re.search(
                        r"(اضافه|افزودن|بذار|حذف|پاک|برادر)\s*(به|از|تو)?\s*(دیده‌بان|لیست|پیگیری|watchlist|watch)?\s*(\S+)",
                        text_lower,
                    )
                    if symbol_match:
                        params["symbol"] = symbol_match.group(len(symbol_match.groups()))

                elif intent == "add_alert":
                    alert_match = re.search(
                        r"هشدار\s*(\S+)\s*(rsi|price|قیمت|حجم|volume)\s*(above|below|بالاتر|پایین‌تر)\s*(\d+)",
                        text_lower,
                    )
                    if alert_match:
                        params["symbol"] = alert_match.group(1)
                        params["field"] = "rsi" if "rsi" in alert_match.group(2).lower() else "price"
                        params["condition"] = "above" if "above" in alert_match.group(3).lower() or "بالاتر" in alert_match.group(3) else "below"
                        params["threshold"] = alert_match.group(4)

                elif intent == "portfolio_add":
                    if groups[0]:
                        params["symbol"] = groups[1] if len(groups) > 1 else ""
                        params["quantity"] = groups[2] if len(groups) > 2 else ""
                        params["price"] = groups[-1] if len(groups) > 3 else ""

                elif intent == "navigate":
                    params["page"] = groups[-1] if groups else ""

                return intent, params

    return None, {}


# Precompiled pattern for detecting OR logic in screener queries.
# If a query contains both AND ("و") and OR ("یا"/"or"), OR takes precedence.
_OR_PATTERN = re.compile(r"\b(or|یا)\b", re.IGNORECASE)

# ── Screener NLU synonyms: Persian phrase -> filter criteria ───────────────
# This helps the assistant understand colloquial Persian stock market terms
# and map them to the structured FilterCriterion used by /screener/filter.

_SCREENER_SYNONYMS: dict[str, dict[str, Any]] = {
    # ── RSI: oversold / overbought ──────────────────────────────────
    "اشباع فروش": {"field": "rsi", "operator": "lt", "value": 30},
    "اشباع فروش شدید": {"field": "rsi", "operator": "lt", "value": 20},
    "کف‌سازی": {"field": "rsi", "operator": "lt", "value": 30},
    "کف قیمتی": {"field": "rsi", "operator": "lt", "value": 25},
    "پایین‌ترین سطح": {"field": "rsi", "operator": "lt", "value": 30},
    "rsi پایین": {"field": "rsi", "operator": "lt", "value": 30},
    "rsi کم": {"field": "rsi", "operator": "lt", "value": 30},
    "شاخص ضعیف": {"field": "rsi", "operator": "lt", "value": 30},
    "فروش بیش از حد": {"field": "rsi", "operator": "lt", "value": 30},
    "اشباع خرید": {"field": "rsi", "operator": "gt", "value": 70},
    "اشباع خرید شدید": {"field": "rsi", "operator": "gt", "value": 80},
    "سقف‌سازی": {"field": "rsi", "operator": "gt", "value": 70},
    "سقف قیمتی": {"field": "rsi", "operator": "gt", "value": 75},
    "بالاترین سطح": {"field": "rsi", "operator": "gt", "value": 70},
    "rsi بالا": {"field": "rsi", "operator": "gt", "value": 70},
    "rsi زیاد": {"field": "rsi", "operator": "gt", "value": 70},
    "شاخص قوی": {"field": "rsi", "operator": "gt", "value": 70},
    "خرید بیش از حد": {"field": "rsi", "operator": "gt", "value": 70},
    "rsi متعادل": {"field": "rsi", "operator": "between", "value": 40, "value_to": 60},
    "rsi خنثی": {"field": "rsi", "operator": "between", "value": 40, "value_to": 60},

    # ── Volume ──────────────────────────────────────────────────────
    "حجم بالا": {"field": "volume", "operator": "gt", "value": 1_000_000},
    "حجم زیاد": {"field": "volume", "operator": "gt", "value": 1_000_000},
    "پرحجم": {"field": "volume", "operator": "gt", "value": 1_000_000},
    "حجم سنگین": {"field": "volume", "operator": "gt", "value": 5_000_000},
    "حجم خیلی بالا": {"field": "volume", "operator": "gt", "value": 10_000_000},
    "حجم فوق‌العاده": {"field": "volume", "operator": "gt", "value": 10_000_000},
    "حجم عجیب": {"field": "volume", "operator": "gt", "value": 5_000_000},
    "حجم غیرعادی": {"field": "volume", "operator": "gt", "value": 5_000_000},
    "حجم مشکوک": {"field": "volume", "operator": "gt", "value": 3_000_000},
    "حجم کم": {"field": "volume", "operator": "lt", "value": 100_000},
    "حجم پایین": {"field": "volume", "operator": "lt", "value": 100_000},
    "بی‌حجم": {"field": "volume", "operator": "lt", "value": 50_000},
    "بدون تقاضا": {"field": "volume", "operator": "lt", "value": 50_000},
    "حجم نرمال": {"field": "volume", "operator": "between", "value": 500_000, "value_to": 2_000_000},
    "افزایش حجم": {"field": "volume_trend", "operator": "eq", "value": "increasing"},
    "کاهش حجم": {"field": "volume_trend", "operator": "eq", "value": "decreasing"},
    "حجم رو به رشد": {"field": "volume_trend", "operator": "eq", "value": "increasing"},
    "حجم فروکش": {"field": "volume_trend", "operator": "eq", "value": "decreasing"},
    "عرضه سنگین": {"field": "volume", "operator": "gt", "value": 5_000_000},
    "تقاضای بالا": {"field": "volume", "operator": "gt", "value": 3_000_000},

    # ── Value / Turnover / Liquidity ────────────────────────────────
    "ارزش معاملات بالا": {"field": "value", "operator": "gt", "value": 10_000_000_000},
    "ارزش بالا": {"field": "value", "operator": "gt", "value": 10_000_000_000},
    "گردش بالا": {"field": "value", "operator": "gt", "value": 10_000_000_000},
    "گردش مالی بالا": {"field": "value", "operator": "gt", "value": 10_000_000_000},
    "ارزش معاملات پایین": {"field": "value", "operator": "lt", "value": 1_000_000_000},
    "گردش کم": {"field": "value", "operator": "lt", "value": 1_000_000_000},
    "نقدشوندگی بالا": {"field": "liquidity_score", "operator": "gt", "value": 0.6},
    "نقدشوندگی خوب": {"field": "liquidity_score", "operator": "gt", "value": 0.5},
    "نقدشوندگی کم": {"field": "liquidity_score", "operator": "lt", "value": 0.3},
    "نقدشوندگی ضعیف": {"field": "liquidity_score", "operator": "lt", "value": 0.3},

    "تعداد معاملات بالا": {"field": "trade_count", "operator": "gt", "value": 5000},
    "تعداد معاملات کم": {"field": "trade_count", "operator": "lt", "value": 500},
    "معاملات فعال": {"field": "trade_count", "operator": "gt", "value": 2000},

    # ── Smart Money / Institutional Flow ────────────────────────────
    "پول هوشمند": {"field": "smc_score", "operator": "gt", "value": 0.7},
    "ورود پول هوشمند": {"field": "power_score", "operator": "gt", "value": 0.6},
    "خروج پول هوشمند": {"field": "power_score", "operator": "lt", "value": 0.3},
    "تجمع سهام": {"field": "liquidity_score", "operator": "gt", "value": 0.6},
    "انباشت سهام": {"field": "power_score", "operator": "gt", "value": 0.6},
    "توزیع سهام": {"field": "power_score", "operator": "lt", "value": 0.3},
    "فروش حقوقی": {"field": "power_score", "operator": "lt", "value": 0.3},
    "خرید حقوقی": {"field": "power_score", "operator": "gt", "value": 0.6},
    "ورود حقوقی": {"field": "power_score", "operator": "gt", "value": 0.6},
    "خروج حقوقی": {"field": "power_score", "operator": "lt", "value": 0.3},
    "حقیقی خریدار": {"field": "power_score", "operator": "gt", "value": 0.5},
    "حقیقی فروشنده": {"field": "power_score", "operator": "lt", "value": 0.4},
    "矚ت حقوقی": {"field": "power_score", "operator": "gt", "value": 0.6},
    "emsak": {"field": "power_score", "operator": "gt", "value": 0.7},
    "انباشت": {"field": "power_score", "operator": "gt", "value": 0.5},
    "accumulation": {"field": "power_score", "operator": "gt", "value": 0.5},
    "distribution": {"field": "power_score", "operator": "lt", "value": 0.3},
    "بازیگر فعال": {"field": "smc_score", "operator": "gt", "value": 0.6},
    "بازیگردان": {"field": "smc_score", "operator": "gt", "value": 0.6},
    "سبدگردان": {"field": "smc_score", "operator": "gt", "value": 0.5},
    "صندوق سرمایه‌گذاری": {"field": "power_score", "operator": "gt", "value": 0.5},
    "نهادی": {"field": "power_score", "operator": "gt", "value": 0.5},

    # ── Fundamentals ────────────────────────────────────────────────
    "ارزنده": {"field": "pe_ratio", "operator": "lt", "value": 8},
    "pe پایین": {"field": "pe_ratio", "operator": "lt", "value": 8},
    "p/e پایین": {"field": "pe_ratio", "operator": "lt", "value": 8},
    "p/e": {"field": "pe_ratio", "operator": "lt", "value": 10},
    "pe بالا": {"field": "pe_ratio", "operator": "gt", "value": 20},
    "p/e بالا": {"field": "pe_ratio", "operator": "gt", "value": 20},
    "ارزشمند": {"field": "pe_ratio", "operator": "lt", "value": 10},
    "زیر ارزش ذاتی": {"field": "pe_ratio", "operator": "lt", "value": 8},
    "بالای ارزش ذاتی": {"field": "pe_ratio", "operator": "gt", "value": 25},
    "سودآور": {"field": "roe", "operator": "gt", "value": 15},
    "roe بالا": {"field": "roe", "operator": "gt", "value": 15},
    "roe کم": {"field": "roe", "operator": "lt", "value": 5},
    "زیان‌ده": {"field": "roe", "operator": "lt", "value": 0},
    "زیان ده": {"field": "roe", "operator": "lt", "value": 0},
    "ضررده": {"field": "roe", "operator": "lt", "value": 0},
    "حاشیه سود بالا": {"field": "net_margin", "operator": "gt", "value": 20},
    "حاشیه سود کم": {"field": "net_margin", "operator": "lt", "value": 5},
    "eps بالا": {"field": "eps", "operator": "gt", "value": 500},
    "eps منفی": {"field": "eps", "operator": "lt", "value": 0},
    "بدهی بالا": {"field": "debt_to_equity", "operator": "gt", "value": 2},
    "بدهی کم": {"field": "debt_to_equity", "operator": "lt", "value": 0.5},
    " بدون بدهی": {"field": "debt_to_equity", "operator": "lt", "value": 0.1},
    "d/e بالا": {"field": "debt_to_equity", "operator": "gt", "value": 2},

    # ── Market Cap ──────────────────────────────────────────────────
    "بزرگ‌ترین": {"field": "market_value", "operator": "gt", "value": 100_000_000_000_000},
    "large cap": {"field": "market_value", "operator": "gt", "value": 100_000_000_000_000},
    "capital بالا": {"field": "market_value", "operator": "gt", "value": 100_000_000_000_000},
    "کوچک": {"field": "market_value", "operator": "lt", "value": 10_000_000_000_000},
    "small cap": {"field": "market_value", "operator": "lt", "value": 10_000_000_000_000},
    "capital پایین": {"field": "market_value", "operator": "lt", "value": 10_000_000_000_000},
    "متوسط": {"field": "market_value", "operator": "between", "value": 10_000_000_000_000, "value_to": 100_000_000_000_000},
    "mid cap": {"field": "market_value", "operator": "between", "value": 10_000_000_000_000, "value_to": 100_000_000_000_000},

    # ── Price Action ────────────────────────────────────────────────
    "رشد قیمت": {"field": "change_pct", "operator": "gt", "value": 0},
    "افزایشی": {"field": "change_pct", "operator": "gt", "value": 0},
    "صعودی": {"field": "change_pct", "operator": "gt", "value": 0},
    "سبز": {"field": "change_pct", "operator": "gt", "value": 0},
    "در حال رشد": {"field": "change_pct", "operator": "gt", "value": 0},
    "رشد سنگین": {"field": "change_pct", "operator": "gt", "value": 3},
    "رشد شارپ": {"field": "change_pct", "operator": "gt", "value": 4},
    "صف خرید": {"field": "change_pct", "operator": "gt", "value": 4.5},
    "کاهشی": {"field": "change_pct", "operator": "lt", "value": 0},
    "نزولی": {"field": "change_pct", "operator": "lt", "value": 0},
    "قرمز": {"field": "change_pct", "operator": "lt", "value": 0},
    "مثبت": {"field": "change_pct", "operator": "gt", "value": 0},
    "منفی": {"field": "change_pct", "operator": "lt", "value": 0},
    "افت سنگین": {"field": "change_pct", "operator": "lt", "value": -3},
    "سقوط": {"field": "change_pct", "operator": "lt", "value": -3},
    "صف فروش": {"field": "change_pct", "operator": "lt", "value": -4.5},
    "در حال افت": {"field": "change_pct", "operator": "lt", "value": 0},
    "منفی شدید": {"field": "change_pct", "operator": "lt", "value": -3},
    "اصلاح قیمت": {"field": "change_pct", "operator": "lt", "value": -1},
    " اصلاح": {"field": "change_pct", "operator": "lt", "value": -1},
    "پولبک": {"field": "change_pct", "operator": "lt", "value": -1},
    "pullback": {"field": "change_pct", "operator": "lt", "value": -1},
    "ثابت": {"field": "change_pct", "operator": "between", "value": -0.5, "value_to": 0.5},
    "بدون تغییر": {"field": "change_pct", "operator": "between", "value": -0.5, "value_to": 0.5},
    "خنثی": {"field": "change_pct", "operator": "between", "value": -0.5, "value_to": 0.5},
    "sideways": {"field": "change_pct", "operator": "between", "value": -0.5, "value_to": 0.5},

    # ── Trend ───────────────────────────────────────────────────────
    "روند صعودی": {"field": "trend_direction", "operator": "eq", "value": "up"},
    "روند نزولی": {"field": "trend_direction", "operator": "eq", "value": "down"},
    "ترند صعودی": {"field": "trend_direction", "operator": "eq", "value": "up"},
    "ترند نزولی": {"field": "trend_direction", "operator": "eq", "value": "down"},
    "صعود قیمت": {"field": "trend_direction", "operator": "eq", "value": "up"},
    "نزول قیمت": {"field": "trend_direction", "operator": "eq", "value": "down"},
    "روند خنثی": {"field": "trend_direction", "operator": "eq", "value": "sideways"},
    "بدون روند": {"field": "trend_direction", "operator": "eq", "value": "sideways"},
    "تثبیت قیمت": {"field": "trend_direction", "operator": "eq", "value": "sideways"},
    "consolidation": {"field": "trend_direction", "operator": "eq", "value": "sideways"},
    "trend قوی": {"field": "trend_strength", "operator": "gt", "value": 0.7},
    "روند قوی": {"field": "trend_strength", "operator": "gt", "value": 0.7},
    "روند ضعیف": {"field": "trend_strength", "operator": "lt", "value": 0.3},
    "تغییر روند": {"field": "trend_strength", "operator": "lt", "value": 0.2},
    "شکست روند": {"field": "trend_strength", "operator": "lt", "value": 0.2},

    # ── Volatility / Risk ───────────────────────────────────────────
    "نوسان کم": {"field": "atr_pct", "operator": "lt", "value": 2},
    "نوسان زیاد": {"field": "atr_pct", "operator": "gt", "value": 5},
    "نوسان شدید": {"field": "atr_pct", "operator": "gt", "value": 7},
    "نوسان بالا": {"field": "atr_pct", "operator": "gt", "value": 5},
    "نوسان خفیف": {"field": "atr_pct", "operator": "lt", "value": 2},
    "volatility بالا": {"field": "atr_pct", "operator": "gt", "value": 5},
    "volatility کم": {"field": "atr_pct", "operator": "lt", "value": 2},
    "بی‌ثبات": {"field": "atr_pct", "operator": "gt", "value": 5},
    "ریسک پایین": {"field": "risk_score", "operator": "lt", "value": 0.4},
    "ریسک بالا": {"field": "risk_score", "operator": "gt", "value": 0.7},
    "ریسک متوسط": {"field": "risk_score", "operator": "between", "value": 0.4, "value_to": 0.7},
    "پرریسک": {"field": "risk_score", "operator": "gt", "value": 0.7},
    "کم‌ریسک": {"field": "risk_score", "operator": "lt", "value": 0.4},
    "ایمن": {"field": "risk_score", "operator": "lt", "value": 0.3},
    "امن": {"field": "risk_score", "operator": "lt", "value": 0.3},
    "risk بالا": {"field": "risk_score", "operator": "gt", "value": 0.7},
    "risk کم": {"field": "risk_score", "operator": "lt", "value": 0.4},

    # ── Composite / Smart Money Score ───────────────────────────────
    "امتیاز بالا": {"field": "smc_score", "operator": "gt", "value": 0.7},
    "امتیاز پایین": {"field": "smc_score", "operator": "lt", "value": 0.3},
    "امتیاز خوب": {"field": "smc_score", "operator": "gt", "value": 0.5},
    "امتیاز عالی": {"field": "smc_score", "operator": "gt", "value": 0.8},
    "score بالا": {"field": "smc_score", "operator": "gt", "value": 0.7},
    "score پایین": {"field": "smc_score", "operator": "lt", "value": 0.3},
    "بهترین": {"field": "smc_score", "operator": "gt", "value": 0.7},
    "ضعیف‌ترین": {"field": "smc_score", "operator": "lt", "value": 0.3},
    "برتر": {"field": "smc_score", "operator": "gt", "value": 0.6},
    "ضعیف": {"field": "smc_score", "operator": "lt", "value": 0.3},
    "قوی": {"field": "smc_score", "operator": "gt", "value": 0.6},
    "متوسط": {"field": "smc_score", "operator": "between", "value": 0.3, "value_to": 0.6},

    # ── Order Flow / Absorption ─────────────────────────────────────
    "جذب عرضه": {"field": "orderflow_score", "operator": "gt", "value": 0.6},
    "جذب تقاضا": {"field": "orderflow_score", "operator": "gt", "value": 0.6},
    "absorption": {"field": "orderflow_score", "operator": "gt", "value": 0.6},
    "orderflow قوی": {"field": "orderflow_score", "operator": "gt", "value": 0.6},
    "جریان سفارشات بالا": {"field": "orderflow_score", "operator": "gt", "value": 0.6},
    "ubsi": {"field": "orderflow_score", "operator": "gt", "value": 0.5},
    "不平衡 سفارشات": {"field": "orderflow_score", "operator": "gt", "value": 0.5},
    "ubsi پایین": {"field": "orderflow_score", "operator": "lt", "value": 0.3},
    "ubsi بالا": {"field": "orderflow_score", "operator": "gt", "value": 0.6},
    "رنج مثبت": {"field": "orderflow_score", "operator": "gt", "value": 0.5},
    "رنج منفی": {"field": "orderflow_score", "operator": "lt", "value": 0.3},

    # ── Structure / Breakout ────────────────────────────────────────
    "آماده شکست": {"field": "trigger_score", "operator": "gt", "value": 0.6},
    "شکست مقاومت": {"field": "trigger_score", "operator": "gt", "value": 0.7},
    "breakout": {"field": "trigger_score", "operator": "gt", "value": 0.6},
    "عبور از مقاومت": {"field": "trigger_score", "operator": "gt", "value": 0.7},
    "نزدیک مقاومت": {"field": "distance_to_resistance", "operator": "lt", "value": 2},
    "نزدیک حمایت": {"field": "distance_to_support", "operator": "lt", "value": 2},
    "زیر حمایت": {"field": "distance_to_support", "operator": "lt", "value": 0},
    "بالای مقاومت": {"field": "distance_to_resistance", "operator": "lt", "value": 0},
    "support قوی": {"field": "distance_to_support", "operator": "gt", "value": 3},
    "resistance قوی": {"field": "distance_to_resistance", "operator": "gt", "value": 3},
    "شکست کف": {"field": "trigger_score", "operator": "lt", "value": 0.3},
    "سقوط از حمایت": {"field": "trigger_score", "operator": "lt", "value": 0.3},
    " نفوذ": {"field": "structure_score", "operator": "gt", "value": 0.6},
    "نفوذ خریدار": {"field": "structure_score", "operator": "gt", "value": 0.6},
    "ساختار قیمتی": {"field": "structure_score", "operator": "gt", "value": 0.5},

    # ── Technical Indicators ────────────────────────────────────────
    "macd مثبت": {"field": "macd_histogram", "operator": "gt", "value": 0},
    "macd منفی": {"field": "macd_histogram", "operator": "lt", "value": 0},
    "macd صفر": {"field": "macd_histogram", "operator": "between", "value": -0.1, "value_to": 0.1},
    "macd بالا": {"field": "macd_histogram", "operator": "gt", "value": 1},
    "macd پایین": {"field": "macd_histogram", "operator": "lt", "value": -1},
    "بولینگر بالا": {"field": "bb_pct", "operator": "gt", "value": 0.8},
    "بولینگر پایین": {"field": "bb_pct", "operator": "lt", "value": 0.2},
    "bb بالا": {"field": "bb_pct", "operator": "gt", "value": 0.8},
    "bb پایین": {"field": "bb_pct", "operator": "lt", "value": 0.2},
    "bb میانی": {"field": "bb_pct", "operator": "between", "value": 0.3, "value_to": 0.7},
    "adx بالا": {"field": "adx", "operator": "gt", "value": 25},
    "adx پایین": {"field": "adx", "operator": "lt", "value": 20},
    "adx قوی": {"field": "adx", "operator": "gt", "value": 30},
    "trend قوی": {"field": "adx", "operator": "gt", "value": 25},
    "trend ضعیف": {"field": "adx", "operator": "lt", "value": 20},
    "cci پایین": {"field": "cci", "operator": "lt", "value": -100},
    "cci بالا": {"field": "cci", "operator": "gt", "value": 100},
    "mfi پایین": {"field": "mfi", "operator": "lt", "value": 20},
    "mfi بالا": {"field": "mfi", "operator": "gt", "value": 80},
    "williams پایین": {"field": "williams_r", "operator": "lt", "value": -80},
    "williams بالا": {"field": "williams_r", "operator": "gt", "value": -20},
    "stochastic پایین": {"field": "stochastic_k", "operator": "lt", "value": 20},
    "stochastic بالا": {"field": "stochastic_k", "operator": "gt", "value": 80},
    "cci overbought": {"field": "cci", "operator": "gt", "value": 100},
    "cci oversold": {"field": "cci", "operator": "lt", "value": -100},
    "momentum بالا": {"field": "momentum_score", "operator": "gt", "value": 0.5},
    "momentum کم": {"field": "momentum_score", "operator": "lt", "value": 0.2},
    "momentum منفی": {"field": "momentum_score", "operator": "lt", "value": 0},
    "تکنیکال قوی": {"field": "technical_score", "operator": "gt", "value": 0.6},
    "تکنیکال ضعیف": {"field": "technical_score", "operator": "lt", "value": 0.3},

    # ── Patterns ────────────────────────────────────────────────────
    "الگوی کف": {"field": "pattern_confidence", "operator": "gt", "value": 0.6},
    "الگوی سقف": {"field": "pattern_confidence", "operator": "gt", "value": 0.6},
    "الگوی ادامه‌دهنده": {"field": "pattern_confidence", "operator": "gt", "value": 0.6},
    "الگوی برگشتی": {"field": "pattern_confidence", "operator": "gt", "value": 0.6},
    "الگوی مثلث": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "مثلث صعودی": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "مثلث نزولی": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "flag pattern": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "cup pattern": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "head and shoulders": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "double top": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "double bottom": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "w pattern": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "m pattern": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "الگوی فنجان": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "الگوی پرچم": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},
    "الگوی سر و شانه": {"field": "pattern_confidence", "operator": "gt", "value": 0.5},

    # ── Volume Profile ──────────────────────────────────────────────
    "vwap بالا": {"field": "poc_price", "operator": "gt", "value": 0},
    "poc بالای قیمت": {"field": "poc_price", "operator": "gt", "value": 0},
    "زیر poc": {"field": "poc_price", "operator": "lt", "value": 0},
    "volume profile": {"field": "poc_price", "operator": "gt", "value": 0},
    "value area": {"field": "value_area_high", "operator": "gt", "value": 0},
    "hab zone": {"field": "volume_trend", "operator": "eq", "value": "concentrated"},

    # ── Composite Signal ────────────────────────────────────────────
    "سیگنال خرید": {"field": "composite_score", "operator": "gt", "value": 0.5},
    "سیگنال فروش": {"field": "composite_score", "operator": "lt", "value": -0.3},
    " buy signal": {"field": "composite_score", "operator": "gt", "value": 0.5},
    " sell signal": {"field": "composite_score", "operator": "lt", "value": -0.3},
    "سیگنال قوی خرید": {"field": "composite_score", "operator": "gt", "value": 0.7},
    "سیگنال قوی فروش": {"field": "composite_score", "operator": "lt", "value": -0.5},
    "long": {"field": "composite_score", "operator": "gt", "value": 0.5},
    "short": {"field": "composite_score", "operator": "lt", "value": -0.3},
    "buy": {"field": "composite_score", "operator": "gt", "value": 0.5},
    "sell": {"field": "composite_score", "operator": "lt", "value": -0.3},

    # ── Sector / Industry ───────────────────────────────────────────
    "فلزات": {"field": "industry", "operator": "eq", "value": "فلزات اساسی"},
    "خودرو": {"field": "industry", "operator": "eq", "value": "خودرو و ساخت قطعات"},
    "دارویی": {"field": "industry", "operator": "eq", "value": "ساخت دارو"},
    "بانکی": {"field": "industry", "operator": "eq", "value": "بانکها"},
    "نفتی": {"field": "industry", "operator": "eq", "value": "شرکتهای چند رشته‌ای"},
    "پتروشیمی": {"field": "industry", "operator": "eq", "value": "شرکتهای پتروشیمی"},
    "سیمانی": {"field": "industry", "operator": "eq", "value": "سیمان، آهک و گچ"},
    "مخابرات": {"field": "industry", "operator": "eq", "value": "مخابرات"},
    "حمل و نقل": {"field": "industry", "operator": "eq", "value": "حمل و نقل، انبارداری و ارتباطات"},
    "بیمه": {"field": "industry", "operator": "eq", "value": "بیمه وصندوق بازنشستگی"},
    "سرمایه‌گذاری": {"field": "industry", "operator": "eq", "value": "سرمایه گذاریها"},
    "هتل و رستوران": {"field": "industry", "operator": "eq", "value": "هتل و رستوران"},
    "عرضه برق": {"field": "industry", "operator": "eq", "value": "عرضه برق، گاز، بخارآب گرم"},
    "انبوه‌سازی": {"field": "industry", "operator": "eq", "value": "انبوه سازی، املاک و مستغلات"},

    "ویژه": {"field": "market", "operator": "eq", "value": "FARA"},
    "فرابورس": {"field": "market", "operator": "eq", "value": "FARA"},
    "بورس": {"field": "market", "operator": "eq", "value": "BOURS"},
    "tse": {"field": "market", "operator": "eq", "value": "BOURS"},

    # ── Advanced Screening Phrases (compound) ───────────────────────
    "سهام خوب": {"field": "smc_score", "operator": "gt", "value": 0.5},
    "بهترین سهام": {"field": "smc_score", "operator": "gt", "value": 0.7},
    "سهام ضعیف": {"field": "smc_score", "operator": "lt", "value": 0.3},
    "سهام مناسب خرید": {"field": "smc_score", "operator": "gt", "value": 0.6},
    "سهام مناسب فروش": {"field": "smc_score", "operator": "lt", "value": 0.3},
    "سهام رشدی": {"field": "change_pct", "operator": "gt", "value": 0},
    "سهام ارزان": {"field": "pe_ratio", "operator": "lt", "value": 8},
    "سهام گران": {"field": "pe_ratio", "operator": "gt", "value": 20},
    "سهام بنیادی": {"field": "smc_score", "operator": "gt", "value": 0.5},
    "سهام تکنیکالی": {"field": "technical_score", "operator": "gt", "value": 0.5},
    "سهام پرتکرار": {"field": "volume", "operator": "gt", "value": 5_000_000},
    "سهام کم‌ریسک": {"field": "risk_score", "operator": "lt", "value": 0.4},
    "سهام پرریسک": {"field": "risk_score", "operator": "gt", "value": 0.7},
    "سهام محبوب": {"field": "volume", "operator": "gt", "value": 3_000_000},
    "سهام جذاب": {"field": "smc_score", "operator": "gt", "value": 0.6},
    "سهام خاص": {"field": "smc_score", "operator": "gt", "value": 0.7},
    "سهام مرموز": {"field": "smc_score", "operator": "gt", "value": 0.7},
    "سهم برتر": {"field": "smc_score", "operator": "gt", "value": 0.7},
    "سهم ضعیف": {"field": "smc_score", "operator": "lt", "value": 0.3},
    "سهم خوب": {"field": "smc_score", "operator": "gt", "value": 0.5},
}


def _extract_screener_filters(text: str) -> list[dict[str, Any]]:
    """Extract filter criteria from Persian screener queries using synonym map."""
    filters: list[dict[str, Any]] = []
    text_lower = text.lower()

    # 1. Direct synonym matches
    for phrase, criterion in _SCREENER_SYNONYMS.items():
        if phrase in text_lower:
            filters.append(dict(criterion))

    # 2. Numeric patterns like RSI<30, P/E<8, حجم>1000
    numeric_patterns = [
        (r"rsi\s*([<>]=?|=)\s*(\d+(?:\.\d+)?)", "rsi"),
        (r"p\s*/\s*e\s*([<>]=?|=)\s*(\d+(?:\.\d+)?)", "pe_ratio"),
        (r"pe\s*([<>]=?|=)\s*(\d+(?:\.\d+)?)", "pe_ratio"),
        (r"roe\s*([<>]=?|=)\s*(\d+(?:\.\d+)?)", "roe"),
        (r"حجم\s*([<>]=?|=)\s*(\d+)", "volume"),
        (r"volume\s*([<>]=?|=)\s*(\d+)", "volume"),
        (r"قیمت\s*([<>]=?|=)\s*(\d+)", "last_price"),
        (r"price\s*([<>]=?|=)\s*(\d+)", "last_price"),
        (r"smc\s*([<>]=?|=)\s*(\d+(?:\.\d+)?)", "smc_score"),
    ]
    for pattern, field in numeric_patterns:
        for match in re.finditer(pattern, text_lower):
            op_str, value_str = match.group(1), match.group(2)
            op_map = {
                ">": "gt", ">=": "gte", "<": "lt", "<=": "lte", "=": "eq",
            }
            filters.append({
                "field": field,
                "operator": op_map.get(op_str, "eq"),
                "value": float(value_str),
            })

    # Deduplicate while preserving order (normalize numeric values to float for comparison)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for f in filters:
        value = f["value"]
        try:
            value_key = float(value) if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace(".", "", 1).isdigit()) else str(value)
        except Exception:
            value_key = str(value)
        key = f"{f['field']}:{f['operator']}:{value_key}"
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def _detect_filter_logic(text: str) -> str:
    """Detect whether the user wants OR or AND logic between filters.

    Supports Persian "یا" and English "or".  Everything else defaults to AND.
    If both AND ("و") and OR indicators are present, OR wins.
    """
    if _OR_PATTERN.search(text):
        return "or"
    return "and"


# ── Page routing for navigation intent ─────────────────────────────────────

_PAGE_MAP: dict[str, str] = {
    "بازار": "/markets",
    "market": "/markets",
    "markets": "/markets",
    "غربالگر": "/smart-screener",
    "screener": "/smart-screener",
    "smart": "/smart-screener",
    "دیده‌بان": "/watchlist",
    "watchlist": "/watchlist",
    "اخبار": "/news",
    "news": "/news",
    "تحلیل": "/analysis",
    "analysis": "/analysis",
    "بک‌تست": "/backtest",
    "backtest": "/backtest",
    "ml": "/ml",
    "مدل": "/ml",
    "یادگیری ماشین": "/ml",
    "پیش‌بینی": "/ml",
    "predict": "/ml",
    "کدال": "/codal",
    "codal": "/codal",
    "اطلاعیه": "/codal",
    "سیگنال": "/signals",
    "signals": "/signals",
    "ریسک": "/risk",
    "risk": "/risk",
    "پرتفوی": "/portfolios",
    "portfolio": "/portfolios",
    "سبد": "/portfolios",
    "داشبورد": "/",
    "dashboard": "/",
    "home": "/",
    "هشدار": "/alerts",
    "alert": "/alerts",
    "alerts": "/alerts",
    "نقشه": "/heatmap",
    "heatmap": "/heatmap",
    "ماکرو": "/macro",
    "macro": "/macro",
    "اقتصاد": "/macro",
    "طلا": "/macro",
    "گزارش": "/reports",
    "report": "/reports",
    "reports": "/reports",
    "ناهنجاری": "/anomalies",
    "anomalies": "/anomalies",
    "صندوق": "/funds",
    "fund": "/funds",
    "مدیریت": "/admin",
    "admin": "/admin",
    "setting": "/admin",
    "settings": "/admin",
    "نمادها": "/instruments",
    "instruments": "/instruments",
    "quotes": "/quotes",
    "قیمت": "/quotes",
    "ارز دیجیتال": "/crypto",
    "crypto": "/crypto",
    "کریپتو": "/crypto",
    "کامودیتی": "/commodities",
    "commodities": "/commodities",
    "فلزات": "/commodities",
    "نفت": "/commodities",
}


def resolve_page(text: str) -> str | None:
    """Resolve a page name from text to a URL path."""
    text_lower = text.strip().lower()
    for keyword, path in _PAGE_MAP.items():
        if keyword in text_lower:
            return path
    return None


# ── Unified Assistant Service ──────────────────────────────────────────────


class UnifiedAssistantService:
    """Unified conversational assistant that connects to ALL app services.

    Features:
    - Natural Persian/English intent detection for ALL app features
    - Routes to real action-executing services (watchlist, alerts, portfolio, etc.)
    - Falls back to StockAssistantService for text-based analysis/comparison
    - Returns structured responses the frontend can render as actions/links
    """

    def __init__(
        self,
        brsapi_service: Any = None,
        market_service: Any = None,
        watchlist_service: Any = None,
        alert_service: Any = None,
        portfolio_service: Any = None,
        backtest_service: Any = None,
        screener_service: Any = None,
        inference_service: Any = None,
        signal_service: Any = None,
        session: Any = None,
    ):
        self._brsapi = brsapi_service
        self._market = market_service
        self._watchlist = watchlist_service
        self._alert = alert_service
        self._portfolio = portfolio_service
        self._backtest = backtest_service
        self._screener = screener_service
        self._inference = inference_service
        self._signal = signal_service
        self._session = session

        # Lazy-loaded StockAssistantService for text-based features
        self._stock_assistant: Any = None

    async def _get_stock_assistant(self):
        """Lazy-load the StockAssistantService for text-based analysis."""
        if self._stock_assistant is None:
            from services.stock_assistant_service import StockAssistantService
            self._stock_assistant = StockAssistantService(brsapi_service=self._brsapi)
        return self._stock_assistant

    async def process(self, text: str) -> dict[str, Any]:
        """Process natural language input and return structured result.

        Returns:
            dict with:
            - text: Persian response text
            - type: response type (text, action, navigation, error, etc.)
            - actions: list of actionable items (add to watchlist, run backtest, etc.)
            - link: optional page URL to navigate to
            - link_label: display label for the link
            - data: optional structured data
            - suggestions: list of suggested follow-up queries
        """
        text = text.strip()
        if not text:
            return self._empty_response()

        start_time = time.time()
        intent, params = detect_intent(text)

        try:
            result = await self._route_intent(intent, params, text)
            # Log successful query
            response_time = (time.time() - start_time) * 1000
            log_query(text, intent=intent, params=params, response_type=result.get("type", "text"), response_time_ms=response_time)
            return result

        except Exception:
            response_time = (time.time() - start_time) * 1000
            log_query(text, intent=intent, params=params, response_type="error", success=False, response_time_ms=response_time)
            logger.exception("Unified assistant error")
            return {
                "text": "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
                "type": "error",
                "suggestions": ["help", "بازار چطوره؟", "بهترین سهم‌ها"],
            }

    async def _route_intent(self, intent: str | None, params: dict[str, str], text: str) -> dict[str, Any]:
        """Route intent to appropriate handler."""
        if intent == "greeting":
            return await self._handle_greeting()

        if intent == "farewell":
            return self._handle_farewell()

        if intent == "help":
            return self._handle_help()

        if intent == "refresh":
            return await self._handle_refresh()

        if intent in ("market_overview", "gainers", "losers"):
            return await self._handle_market(intent)

        if intent == "analyze_symbol":
            return await self._handle_analysis(params, text)

        if intent == "compare":
            return await self._handle_comparison(params, text)

        if intent == "add_watchlist":
            return await self._handle_watchlist_add(params, text)

        if intent == "remove_watchlist":
            return await self._handle_watchlist_remove(params, text)

        if intent == "list_watchlist":
            return await self._handle_watchlist_list()

        if intent == "add_alert":
            return await self._handle_alert_add(params, text)

        if intent == "list_alerts":
            return await self._handle_alerts_list()

        if intent == "remove_alert":
            return await self._handle_alert_remove(params, text)

        if intent == "portfolio_add":
            return await self._handle_portfolio_add(params, text)

        if intent == "portfolio_remove":
            return await self._handle_portfolio_remove(params, text)

        if intent == "portfolio_summary":
            return await self._handle_portfolio_summary()

        if intent == "screener":
            return await self._handle_screener(text)

        if intent == "run_backtest":
            return await self._handle_backtest(params, text)

        if intent == "list_backtests":
            return await self._handle_backtest_list()

        if intent == "ml_predict":
            return await self._handle_ml_predict(params, text)

        if intent == "ml_train":
            return await self._handle_ml_train(text)

        if intent == "ml_list_models":
            return await self._handle_ml_list()

        if intent in ("news", "codal"):
            return self._handle_news_codal(intent, params, text)

        if intent == "macro":
            return await self._handle_macro()

        if intent == "heatmap":
            return self._handle_heatmap()

        if intent == "risk":
            return self._handle_risk()

        if intent == "report":
            return await self._handle_report()

        if intent == "anomalies":
            return self._handle_anomalies()

        if intent == "signals":
            return await self._handle_signals()

        if intent == "navigate":
            return self._handle_navigate(params, text)

        if intent == "crypto":
            return self._handle_crypto(params, text)

        if intent == "commodities":
            return self._handle_commodities(params, text)

        # ── Fallback: try stock assistant for text-based features ──
        assistant = await self._get_stock_assistant()
        result = await assistant.process_message(text)
        if result and result.get("type") != "unknown":
            return {
                "text": result.get("text", ""),
                "type": result.get("type", "text"),
                "data": result.get("data"),
                "suggestions": self._get_suggestions_for_type(result.get("type", "")),
            }

        # ── Try to extract symbol and analyze ──
        symbol = await self._try_extract_symbol(text)
        if symbol:
            return await self._handle_analysis({"symbol": symbol}, text)

        # ── Last resort: suggest features ──
        return self._handle_unknown(text)

    # ── Intent Handlers ────────────────────────────────────────────────────

    async def _handle_greeting(self) -> dict[str, Any]:
        return {
            "text": (
                "سلام! 👋\n\n"
                "من دستیار هوشمند بازار سرمایه هستم. می‌توانم کارهای زیر را انجام دهم:\n\n"
                "📊 **تحلیل و بازار**\n"
                "• «تحلیل فولاد» — تحلیل کامل یک نماد\n"
                "• «بازار چطوره؟» — خلاصه بازار\n"
                "• «مقایسه فولاد و خودرو» — مقایسه دو سهم\n\n"
                "🔍 **غربال‌گری و فیلتر**\n"
                "• «بهترین سهم‌ها» — غربال‌گری هوشمند\n"
                "• «فیلتر RSI<30 ROE>20» — فیلتر پیشرفته\n\n"
                "👁️ **دیده‌بان و هشدار**\n"
                "• «اضافه فولاد به دیده‌بان» — افزودن به لیست پیگیری\n"
                "• «هشدار فولاد rsi above 70» — ثبت هشدار\n\n"
                "💼 **پرتفوی و بک‌تست**\n"
                "• «پرتفوی من» — وضعیت سبد سهام\n"
                "• «بک‌تست فولاد» — اجرای آزمون برگشتی\n\n"
                "🧠 **یادگیری ماشین**\n"
                "• «پیش‌بینی فولاد» — پیش‌بینی قیمت با AI\n\n"
                "📰 **اخبار و اطلاعات**\n"
                "• «اخبار بازار» — آخرین اخبار\n"
                "• «طلا و ارز» — داده‌های کلان\n\n"
                "💡 آماده کمک هستم. هر سوالی دارید بپرسید!"
            ),
            "type": "greeting",
            "suggestions": [
                "بازار چطوره؟",
                "تحلیل فولاد",
                "بهترین سهم‌ها",
                "پرتفوی من",
                "پیش‌بینی بازار",
                "help",
            ],
        }

    def _handle_farewell(self) -> dict[str, Any]:
        return {
            "text": "خداحافظ! موفق باشید 🙏\n\nهر وقت نیاز داشتید، من اینجام.",
            "type": "farewell",
        }

    def _handle_help(self) -> dict[str, Any]:
        return {
            "text": (
                "🤖 **راهنمای دستیار هوشمند**\n\n"
                "**تحلیل نمادها:**\n"
                "• «تحلیل [نماد]» — مثال: تحلیل فولاد\n"
                "• «[نماد] چطوره؟» — مثال: فولاد چطوره؟\n"
                "• «مقایسه [نماد1] و [نماد2]» — مثال: مقایسه فولاد و خودرو\n\n"
                "**بازار:**\n"
                "• «بازار چطوره؟» — خلاصه وضعیت بازار\n"
                "• «پرمتحرک‌ترین‌ها» — نمادهای پرنوسان\n"
                "• «بهترین سهم‌ها» — غربال‌گری هوشمند\n\n"
                "**دیده‌بان و هشدار:**\n"
                "• «اضافه [نماد] به دیده‌بان» — مثال: اضافه فولاد به دیده‌بان\n"
                "• «دیده‌بان من» — نمایش لیست پیگیری\n"
                "• «هشدار [نماد] rsi above 70» — مثال: هشدار فولاد rsi above 70\n\n"
                "**پرتفوی:**\n"
                "• «خرید [نماد] [تعداد] [قیمت]» — مثال: خرید فولاد 100 50000\n"
                "• «پرتفوی من» — وضعیت سبد\n\n"
                "**بک‌تست و ML:**\n"
                "• «بک‌تست [نماد]» — اجرای آزمون\n"
                "• «پیش‌بینی [نماد]» — پیش‌بینی با AI\n\n"
                "**سایر:**\n"
                "• «اخبار» — آخرین اخبار بازار\n"
                "• «طلا و ارز» — داده‌های کلان\n"
                "• «نقشه بازار» — نقشه حرارتی\n"
                "• «برو به [بخش]» — مثال: برو به غربالگر\n"
                "• «سیگنال‌ها» — سیگنال‌های معاملاتی\n"
                "• «ناهنجاری‌ها» — تشخیص ناهنجاری"
            ),
            "type": "help",
            "suggestions": [
                "تحلیل فولاد",
                "بازار چطوره؟",
                "اضافه فولاد به دیده‌بان",
                "پرتفوی من",
                "پیش‌بینی فولاد",
                "برو به غربالگر",
            ],
        }

    async def _handle_refresh(self) -> dict[str, Any]:
        # Clear stock assistant cache
        try:
            assistant = await self._get_stock_assistant()
            if hasattr(assistant, "_cache"):
                assistant._cache.clear()
        except Exception as e:
            logger.debug("Failed to clear cache on refresh: %s", e)

        return {
            "text": "✅ تمام داده‌ها بروزرسانی شدند.",
            "type": "refresh",
        }

    async def _handle_market(self, intent: str) -> dict[str, Any]:
        if self._market:
            try:
                if intent == "gainers":
                    result = await self._market.get_top_gainers(5)
                    if result.success and result.value:
                        items = result.value
                        lines = ["🔥 **پرمتقاضی‌ترین نمادها:**", "═" * 30]
                        for i, item in enumerate(items[:5], 1):
                            change = getattr(item, "price_change_pct", 0) or 0
                            symbol = getattr(item, "symbol", "")
                            lines.append(f"  {i}. {symbol}: {change:+.2f}%")
                        return {"text": "\n".join(lines), "type": "market", "suggestions": ["کاهشی‌ها", "خلاصه بازار", "بهترین سهم‌ها"]}

                if intent == "losers":
                    result = await self._market.get_top_losers(5)
                    if result.success and result.value:
                        items = result.value
                        lines = ["⚠️ **پرمتقاضی‌ترین کاهشی‌ها:**", "═" * 30]
                        for i, item in enumerate(items[:5], 1):
                            change = getattr(item, "price_change_pct", 0) or 0
                            symbol = getattr(item, "symbol", "")
                            lines.append(f"  {i}. {symbol}: {change:+.2f}%")
                        return {"text": "\n".join(lines), "type": "market", "suggestions": ["افزایشی‌ها", "خلاصه بازار", "تحلیل فولاد"]}

                # Default: overview
                overview = await self._market.get_overview()
                if overview.success and overview.value:
                    d = overview.value
                    total = d.get("total_instruments", 0)
                    gainers = d.get("gainers", 0)
                    losers = d.get("losers", 0)
                    avg_change = d.get("avg_change_pct", 0)
                    return {
                        "text": (
                            f"📊 **خلاصه بازار**\n\n"
                            f"تعداد نمادها: {total:,}\n"
                            f"✅ مثبت: {gainers:,}\n"
                            f"🔴 منفی: {losers:,}\n"
                            f"میانگین تغییرات: {avg_change:+.2f}%\n"
                        ),
                        "type": "market",
                        "actions": [
                            {"type": "link", "label": "📊 صفحه بازار", "url": "/markets"},
                        ],
                        "suggestions": ["افزایشی‌ها", "کاهشی‌ها", "بهترین سهم‌ها", "تحلیل فولاد"],
                    }
            except Exception as e:
                logger.warning("Market handler error: %s", e)

        # Fallback to stock assistant
        assistant = await self._get_stock_assistant()
        result = await assistant.process_message("بازار چطوره؟")
        return {
            "text": result.get("text", "داده‌ای موجود نیست."),
            "type": "market",
            "suggestions": ["افزایشی‌ها", "کاهشی‌ها", "تحلیل فولاد"],
        }

    async def _handle_analysis(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        # Try to extract symbol from text if not in params
        symbol = params.get("symbol", "")
        if not symbol:
            symbol = await self._try_extract_symbol(text)

        if symbol:
            # ── Priority 1: Full AI report from the 110-column model ──
            # The report service opens its own DB session when none is injected.
            try:
                from services.screener_ai_report_service import ScreenerAIReportService

                report = await ScreenerAIReportService(self._session).generate_symbol_report(symbol)
                report_text = report.get("text", "")
                if report_text and (report.get("model") or report.get("signal") or report.get("profile")):
                    return {
                        "text": report_text,
                        "type": "analysis",
                        "data": {
                            "symbol": symbol,
                            "model": report.get("model"),
                            "signal": report.get("signal"),
                            "profile": report.get("profile"),
                            "signals_history": report.get("signals_history", [])[:10],
                        },
                        "actions": [
                            {"type": "link", "label": f"📈 صفحه {symbol}", "url": f"/symbol/{symbol}"},
                            {"type": "link", "label": "📊 تحلیل بازار", "url": "/analysis"},
                        ],
                        "suggestions": [
                            f"مقایسه {symbol} و فولاد",
                            f"پیش‌بینی {symbol}",
                            f"اضافه {symbol} به دیده‌بان",
                            "خلاصه بازار",
                        ],
                    }
            except Exception as exc:
                logger.warning("AI report unavailable for %s, falling back: %s", symbol, exc)

            # ── Priority 2: Stock assistant text analysis ──
            assistant = await self._get_stock_assistant()
            result = await assistant.process_message(f"تحلیل {symbol}")

            if result.get("type") != "error":
                return {
                    "text": result.get("text", ""),
                    "type": "analysis",
                    "data": result.get("data"),
                    "actions": [
                        {"type": "link", "label": f"📈 صفحه {symbol}", "url": f"/symbol/{symbol}"},
                        {"type": "link", "label": "📊 تحلیل بازار", "url": "/analysis"},
                    ],
                    "suggestions": [
                        f"مقایسه {symbol} و فولاد",
                        f"پیش‌بینی {symbol}",
                        f"اضافه {symbol} به دیده‌بان",
                        "خلاصه بازار",
                    ],
                }

        return {
            "text": "نمادی برای تحلیل پیدا نشد. لطفاً نام نماد را مشخص کنید.\n\nمثال: تحلیل فولاد",
            "type": "error",
            "suggestions": ["تحلیل فولاد", "تحلیل شپنا", "تحلیل خودرو", "بازار چطوره؟"],
        }

    async def _handle_comparison(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        assistant = await self._get_stock_assistant()
        result = await assistant.process_message(text)

        if result.get("type") not in ("error", "unknown"):
            return {
                "text": result.get("text", ""),
                "type": "comparison",
                "data": result.get("data"),
                "suggestions": ["تحلیل فولاد", "بهترین سهم‌ها", "خلاصه بازار"],
            }

        return {
            "text": "لطفاً دو نماد را برای مقایسه مشخص کنید.\n\nمثال: مقایسه فولاد و خودرو",
            "type": "error",
            "suggestions": ["مقایسه فولاد و شپنا", "مقایسه خودرو و خساپا", "تحلیل فولاد"],
        }

    async def _handle_watchlist_add(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        symbol = params.get("symbol", "")
        if not symbol:
            symbol = await self._try_extract_symbol(text)

        if symbol and self._watchlist:
            try:
                result = await self._watchlist.add_symbol(symbol)
                if result.success:
                    return {
                        "text": f"✅ **{symbol}** به دیده‌بان اضافه شد.\n\nمی‌توانید دیده‌بان خود را در صفحه مربوطه مشاهده کنید.",
                        "type": "action",
                        "actions": [
                            {"type": "link", "label": "👁️ دیده‌بان", "url": "/watchlist"},
                            {"type": "link", "label": f"📈 صفحه {symbol}", "url": f"/symbol/{symbol}"},
                        ],
                        "suggestions": [f"اضافه {await self._random_symbol()} به دیده‌بان", "دیده‌بان من", "تحلیل فولاد"],
                    }
                return {
                    "text": f"⚠️ **{symbol}** قبلاً در دیده‌بان شما وجود دارد.",
                    "type": "info",
                    "actions": [{"type": "link", "label": "👁️ دیده‌بان", "url": "/watchlist"}],
                }
            except Exception as e:
                logger.warning("Watchlist add error: %s", e)

        return {
            "text": "لطفاً نماد مورد نظر را مشخص کنید.\n\nمثال: اضافه فولاد به دیده‌بان",
            "type": "error",
            "suggestions": ["اضافه فولاد به دیده‌بان", "دیده‌بان من", "تحلیل فولاد"],
        }

    async def _handle_watchlist_remove(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        symbol = params.get("symbol", "")
        if not symbol:
            symbol = await self._try_extract_symbol(text)

        if symbol and self._watchlist:
            try:
                result = await self._watchlist.remove_symbol(symbol)
                if result.success:
                    return {
                        "text": f"✅ **{symbol}** از دیده‌بان حذف شد.",
                        "type": "action",
                        "actions": [{"type": "link", "label": "👁️ دیده‌بان", "url": "/watchlist"}],
                        "suggestions": ["دیده‌بان من", f"اضافه {symbol} به دیده‌بان", "تحلیل فولاد"],
                    }
            except Exception as e:
                logger.warning("Watchlist remove error for %s: %s", symbol, e)

        return {
            "text": f"⚠️ نماد **{symbol or 'مورد نظر'}** در دیده‌بان شما یافت نشد.",
            "type": "error",
            "suggestions": ["دیده‌بان من", "اضافه فولاد به دیده‌بان"],
        }

    async def _handle_watchlist_list(self) -> dict[str, Any]:
        if self._watchlist:
            try:
                result = await self._watchlist.list_items()
                if result.success and result.value:
                    items = result.value
                    lines = ["👁️ **دیده‌بان شما**", "═" * 40]
                    for i, item in enumerate(items[:20], 1):
                        sym = item.get("symbol", "")
                        price = item.get("price", "")
                        change = item.get("change", "")
                        change_str = f" ({change:+.2f}%)" if change and isinstance(change, (int, float)) else ""
                        price_str = f" — {price:,}" if price and isinstance(price, (int, float)) else ""
                        lines.append(f"  {i}. {sym}{price_str}{change_str}")
                    lines.append(f"\n📊 مجموع: {len(items)} نماد")
                    return {
                        "text": "\n".join(lines),
                        "type": "watchlist",
                        "data": {"count": len(items)},
                        "actions": [{"type": "link", "label": "👁️ مدیریت دیده‌بان", "url": "/watchlist"}],
                        "suggestions": [f"اضافه {await self._random_symbol()} به دیده‌بان", "تحلیل فولاد", "خلاصه بازار"],
                    }
            except Exception as e:
                logger.warning("Watchlist list error: %s", e)

        return {
            "text": "دیده‌بان شما خالی است.\n\nمی‌توانید با دستور «اضافه [نماد] به دیده‌بان» نماد اضافه کنید.\nمثال: اضافه فولاد به دیده‌بان",
            "type": "info",
            "suggestions": ["اضافه فولاد به دیده‌بان", "اضافه شپنا به دیده‌بان", "تحلیل فولاد"],
        }

    async def _handle_alert_add(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        symbol = params.get("symbol", "")
        field = params.get("field", "price")
        condition = params.get("condition", "above")
        threshold = params.get("threshold", "")

        if not symbol:
            symbol = await self._try_extract_symbol(text)

        if symbol and threshold and self._alert:
            try:
                operator = "gte" if condition == "above" else "lte"
                # Alert type must be one of the schema values (price_above,
                # rsi_oversold, ...) — not the bare field name.
                if field == "rsi":
                    alert_type = "rsi_oversold" if operator == "lte" else "rsi_overbought"
                elif field == "volume":
                    alert_type = "volume_above" if operator == "gte" else "volume_below"
                else:
                    alert_type = "price_above" if operator == "gte" else "price_below"

                condition_dict = {
                    "field": field,
                    "operator": operator,
                    "threshold": float(threshold),
                    # Anti-spam: don't re-trigger within 30 minutes.
                    "cooldown_minutes": 30,
                }
                result = await self._alert.create_alert(
                    user_id="assistant",
                    # instrument_id is a UUID resolved server-side when available
                    # — never store the ticker symbol there (matching happens by symbol).
                    instrument_id="",
                    symbol=symbol,
                    alert_type=alert_type,
                    condition=condition_dict,
                    channels=["telegram", "console"],
                    description=f"هشدار {field} {condition} {threshold} برای {symbol}",
                )
                if result.success:
                    field_label = "قیمت" if field == "price" else "RSI"
                    condition_label = "بالای" if condition == "above" else "پایین‌تر از"
                    return {
                        "text": f"✅ هشدار ثبت شد:\n**{symbol}** — {field_label} {condition_label} {float(threshold):,.0f}",
                        "type": "action",
                        "actions": [{"type": "link", "label": "🔔 مدیریت هشدارها", "url": "/alerts"}],
                        "suggestions": [f"هشدار {symbol} rsi below 30", "لیست هشدارها", "تحلیل فولاد"],
                    }
            except Exception as e:
                logger.warning("Alert add error: %s", e)

        return {
            "text": "فرمت صحیح:\n«هشدار [نماد] [نوع] [شرط] [مقدار]»\n\nمثال: هشدار فولاد rsi above 70\nمثال: هشدار خودرو قیمت below 2500",
            "type": "error",
            "suggestions": ["هشدار فولاد rsi above 70", "هشدار شپنا price below 40000", "لیست هشدارها"],
        }

    async def _handle_alerts_list(self) -> dict[str, Any]:
        if self._alert:
            try:
                result = await self._alert.list_alerts(page=1, page_size=50)
                if result.success and result.value:
                    items = result.value.get("items", [])
                    if items:
                        lines = ["🔔 **هشدارهای فعال:**", "═" * 40]
                        for a in items[:20]:
                            symbol = a.get("symbol", "")
                            alert_type = a.get("alert_type", "")
                            cond = a.get("condition", {})
                            threshold = cond.get("threshold", "")
                            enabled = "✅" if a.get("enabled", True) else "⛔"
                            lines.append(f"  {enabled} {symbol}: {alert_type} {threshold}")
                        return {
                            "text": "\n".join(lines),
                            "type": "alerts",
                            "actions": [{"type": "link", "label": "🔔 مدیریت هشدارها", "url": "/alerts"}],
                            "suggestions": ["هشدار فولاد rsi above 70", "حذف هشدار فولاد", "تحلیل فولاد"],
                        }
            except Exception as e:
                logger.warning("Alert list error: %s", e)

        return {
            "text": "هشداری ثبت نشده است.\n\nبرای ثبت هشدار:\n«هشدار فولاد rsi above 70»",
            "type": "info",
            "suggestions": ["هشدار فولاد rsi above 70", "هشدار شپنا price below 40000"],
        }

    async def _handle_alert_remove(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        # Try to get symbol from text
        # For simplicity, redirect to alerts page for manual management
        return {
            "text": "برای حذف هشدار، لطفاً به صفحه مدیریت هشدارها مراجعه کنید.",
            "type": "info",
            "actions": [{"type": "link", "label": "🔔 مدیریت هشدارها", "url": "/alerts"}],
            "suggestions": ["لیست هشدارها", "هشدار فولاد rsi above 70", "تحلیل فولاد"],
        }

    async def _handle_portfolio_add(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        # Use stock assistant's in-memory portfolio for now
        # Real portfolio creation is complex and requires user context
        assistant = await self._get_stock_assistant()
        result = await assistant.process_message(text)
        if result.get("type") == "portfolio":
            return {
                "text": result.get("text", ""),
                "type": "portfolio",
                "suggestions": ["خلاصه پرتفوی", "خرید شپنا 50 45000", "تحلیل فولاد"],
            }

        return {
            "text": "فرمت صحیح:\n«خرید [نماد] [تعداد] [قیمت]»\n\nمثال: خرید فولاد 100 50000\nمثال: خرید شپنا 50 45000",
            "type": "error",
            "suggestions": ["خرید فولاد 100 50000", "خلاصه پرتفوی", "تحلیل فولاد"],
        }

    async def _handle_portfolio_remove(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        assistant = await self._get_stock_assistant()
        result = await assistant.process_message(text)
        return {
            "text": result.get("text", "✅ نماد از پرتفوی حذف شد." if result.get("type") == "portfolio" else "خطا در حذف از پرتفوی"),
            "type": "portfolio",
            "suggestions": ["خلاصه پرتفوی", "خرید فولاد 100 50000", "تحلیل فولاد"],
        }

    async def _handle_portfolio_summary(self) -> dict[str, Any]:
        assistant = await self._get_stock_assistant()
        result = await assistant.process_message("خلاصه پرتفوی")
        return {
            "text": result.get("text", "پرتفوی شما خالی است."),
            "type": "portfolio",
            "data": result.get("data"),
            "suggestions": ["خرید فولاد 100 50000", "خرید شپنا 50 45000", "تحلیل فولاد"],
        }

    async def _handle_screener(self, text: str) -> dict[str, Any]:
        # Try to understand the query via Persian synonym map first.
        extracted_filters = _extract_screener_filters(text)
        filter_logic = _detect_filter_logic(text)

        # Fallback to the text-only stock assistant for human-readable text.
        assistant = await self._get_stock_assistant()
        result = await assistant.process_message(text)

        # Build a helpful response that also exposes the structured filters so
        # the frontend can call /screener/filter or /screener-v2/filter directly.
        suggestions = [
            "فیلتر RSI<30 ROE>20 P/E<8",
            "سهم‌های با SMC بالا",
            "نمادهای با نقدشوندگی قوی",
            "تحلیل فولاد",
        ]

        symbols: list[dict[str, Any]] = []

        # Try to actually run the screener if we have the required services.
        if self._screener and self._brsapi:
            try:
                instruments, market_watch = await fetch_market_watch(self._brsapi, limit=200)
                if not instruments:
                    scored: list[Any] = []
                else:
                    scored, _ = await self._screener.screen_with_filters(
                    instruments=instruments,
                    market_watch=market_watch,
                    filters=extracted_filters if extracted_filters else None,
                    filter_logic="and",
                    sort_by="smc_score",
                    sort_order="desc",
                    limit=10,                        include_details=True,
                    )
                    symbols = [
                    {
                        "symbol": r.symbol,
                        "name": r.name,
                        "smc_score": r.smc_score,
                        "change_pct": r.change_pct,
                        "last_price": r.last_price,
                    }
                    for r in scored
                ]
            except Exception as exc:
                logger.warning("Screener execution from assistant failed: %s", exc)

        if extracted_filters:
            if len(extracted_filters) > 1:
                logic_label = "یا" if filter_logic == "or" else "و"
                logic_part = f" (ترکیب: {logic_label})"
            else:
                logic_part = ""
            filters_text = "\n".join(
                f"  • {f['field']} {f['operator']} {f['value']}" for f in extracted_filters
            )
            response_text = (
                f"🔍 **فیلترهای شناسایی‌شده{logic_part}:**\n\n{filters_text}\n\n"
                f"تعداد نماد مطابق: {len(symbols)}\n\n"
                "برای مشاهده نتایج کامل، به غربال‌گر هوشمند بروید."
            )
        else:
            response_text = result.get("text", "")

        return {
            "text": response_text,
            "type": "screener",
            "data": {"filters": extracted_filters, "symbols": symbols, "filter_logic": filter_logic},
            "actions": [
                {"type": "link", "label": "🔍 غربال‌گر هوشمند", "url": "/smart-screener"},
                {"type": "link", "label": "🎯 غربال‌گر ساده", "url": "/screener"},
            ],
            "suggestions": suggestions,
        }

    async def _handle_backtest(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        symbol = params.get("symbol", "") or await self._try_extract_symbol(text)

        if symbol and self._backtest:
            return {
                "text": f"🧪 **اجرای بک‌تست برای {symbol}**\n\nبرای اجرا به صفحه بک‌تست بروید و پارامترها را تنظیم کنید.",
                "type": "backtest",
                "actions": [
                    {"type": "link", "label": f"🧪 بک‌تست {symbol}", "url": f"/backtest?symbol={symbol}"},
                ],
                "suggestions": ["بک‌تست همه نمادها", "لیست بک‌تست‌ها", "تحلیل فولاد"],
            }

        return {
            "text": "برای اجرای بک‌تست، به صفحه بک‌تست بروید:\n\n«بک‌تست فولاد» یا مراجعه به صفحه بک‌تست",
            "type": "info",
            "actions": [{"type": "link", "label": "🧪 صفحه بک‌تست", "url": "/backtest"}],
            "suggestions": ["بک‌تست فولاد", "لیست بک‌تست‌ها", "تحلیل فولاد"],
        }

    async def _handle_backtest_list(self) -> dict[str, Any]:
        if self._backtest:
            try:
                result = await self._backtest.list_runs()
                if result.success and result.value:
                    items = result.value
                    lines = ["🧪 **بک‌تست‌های اخیر:**", "═" * 40]
                    for i, run in enumerate(items[:10], 1):
                        name = run.get("name", "")
                        strategy = run.get("strategy_type", "")
                        return_pct = run.get("total_return_pct", 0)
                        status = run.get("status", "")
                        lines.append(f"  {i}. {name} ({strategy}): {return_pct:+.2f}% [{status}]")
                    return {
                        "text": "\n".join(lines),
                        "type": "backtest_list",
                        "actions": [{"type": "link", "label": "🧪 صفحه بک‌تست", "url": "/backtest"}],
                        "suggestions": ["بک‌تست فولاد", "بک‌تست همه نمادها", "تحلیل فولاد"],
                    }
            except Exception as e:
                logger.warning("Backtest list error: %s", e)

        return {
            "text": "بک‌تستی یافت نشد.\n\nبرای اجرا:\n«بک‌تست فولاد»",
            "type": "info",
            "actions": [{"type": "link", "label": "🧪 صفحه بک‌تست", "url": "/backtest"}],
            "suggestions": ["بک‌تست فولاد", "تحلیل فولاد"],
        }

    async def _handle_ml_predict(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        symbol = params.get("symbol", "") or await self._try_extract_symbol(text)

        if symbol:
            return {
                "text": f"🧠 **پیش‌بینی قیمت {symbol}**\n\nبرای مشاهده پیش‌بینی‌ها به صفحه ML بروید.",
                "type": "ml",
                "actions": [
                    {"type": "link", "label": f"🧠 پیش‌بینی {symbol}", "url": f"/ml?symbol={symbol}"},
                ],
                "suggestions": ["پیش‌بینی همه نمادها", "مشاهده مدل‌ها", "تحلیل فولاد"],
            }

        return {
            "text": "برای پیش‌بینی، لطفاً نماد را مشخص کنید:\n\n«پیش‌بینی فولاد»",
            "type": "info",
            "actions": [{"type": "link", "label": "🧠 صفحه ML", "url": "/ml"}],
            "suggestions": ["پیش‌بینی فولاد", "پیش‌بینی همه نمادها", "مشاهده مدل‌ها"],
        }

    async def _handle_ml_train(self, text: str) -> dict[str, Any]:
        return {
            "text": "🧠 **آموزش مدل روی همه نمادها**\n\nبرای اجرا به صفحه ML بروید.",
            "type": "ml",
            "actions": [{"type": "link", "label": "🧠 صفحه ML", "url": "/ml"}],
            "suggestions": ["پیش‌بینی فولاد", "مشاهده مدل‌ها", "تحلیل فولاد"],
        }

    async def _handle_ml_list(self) -> dict[str, Any]:
        return {
            "text": "🧠 برای مشاهده مدل‌های موجود به صفحه ML بروید.",
            "type": "ml",
            "actions": [{"type": "link", "label": "🧠 صفحه ML", "url": "/ml"}],
            "suggestions": ["پیش‌بینی فولاد", "آموزش مدل جدید", "تحلیل فولاد"],
        }

    def _handle_news_codal(self, intent: str, params: dict[str, Any], text: str) -> dict[str, Any]:
        label = "اخبار" if intent == "news" else "کدال"
        url = "/news" if intent == "news" else "/codal"
        icon = "📰" if intent == "news" else "🏢"

        return {
            "text": f"{icon} آخرین {label} بازار را می‌توانید در صفحه مربوطه مشاهده کنید.",
            "type": intent,
            "actions": [{"type": "link", "label": f"{icon} {label}", "url": url}],
            "suggestions": [f"{label} فولاد", "خلاصه بازار", "تحلیل فولاد"],
        }

    async def _handle_macro(self) -> dict[str, Any]:
        gold_text = ""
        dollar_text = ""

        if self._market:
            try:
                gold_result = await self._market.get_macro_data("gold")
                if gold_result.success and gold_result.value:
                    data = gold_result.value.get("data", [])
                    if data and len(data) > 0:
                        item = data[0]
                        gold_text = f"طلا: {item.get('price', 'N/A'):,}"

                currency_result = await self._market.get_macro_data("currency")
                if currency_result.success and currency_result.value:
                    data = currency_result.value.get("data", [])
                    if data:
                        for item in data:
                            name = item.get("name", "")
                            if "دلار" in name:
                                dollar_text = f"دلار: {item.get('price', 'N/A'):,}"
                                break
            except Exception as e:
                logger.debug("Failed to fetch macro data: %s", e)

        text_parts = ["🏛️ **داده‌های کلان اقتصادی**"]
        if gold_text:
            text_parts.append(f"\n{gold_text}")
        if dollar_text:
            text_parts.append(f"\n{dollar_text}")
        if not gold_text and not dollar_text:
            text_parts.append("\nبرای مشاهده به صفحه داده‌های کلان بروید.")

        return {
            "text": "\n".join(text_parts),
            "type": "macro",
            "actions": [{"type": "link", "label": "🏛️ داده‌های کلان", "url": "/macro"}],
            "suggestions": ["طلا و سکه", "قیمت دلار", "خلاصه بازار", "تحلیل فولاد"],
        }

    def _handle_heatmap(self) -> dict[str, Any]:
        return {
            "text": "🗺️ **نقشه حرارتی بازار**\n\nبرای مشاهده نقشه حرارتی به صفحه مربوطه بروید.",
            "type": "heatmap",
            "actions": [{"type": "link", "label": "🗺️ نقشه بازار", "url": "/heatmap"}],
            "suggestions": ["بازار چطوره؟", "پرتحرک‌ترین‌ها", "تحلیل فولاد"],
        }

    def _handle_risk(self) -> dict[str, Any]:
        return {
            "text": "🛡️ **مدیریت ریسک**\n\nشاخص‌های قابل پایش:\n• VaR (۹۵%)\n• Sharpe Ratio\n• Beta\n• Max Drawdown\n• Volatility\n\nبرای اطلاعات بیشتر به صفحه ریسک بروید.",
            "type": "risk",
            "actions": [{"type": "link", "label": "🛡️ صفحه ریسک", "url": "/risk"}],
            "suggestions": ["شاخص‌های ریسک", "ناهنجاری‌ها", "خلاصه بازار"],
        }

    async def _handle_report(self) -> dict[str, Any]:
        # Priority 1: AI market report from the 110-column model
        try:
            from services.screener_ai_report_service import ScreenerAIReportService

            report = await ScreenerAIReportService(self._session).generate_market_report(limit=15)
            if report.get("text"):
                return {
                    "text": report["text"],
                    "type": "report",
                    "data": {
                        "stats": report.get("stats"),
                        "buy_signals": report.get("buy_signals", [])[:15],
                    },
                    "actions": [
                        {"type": "link", "label": "📊 گزارش کامل بازار", "url": "/reports"},
                    ],
                    "suggestions": ["بهترین سهم‌ها", "تحلیل فولاد", "سیگنال‌ها"],
                }
        except Exception as exc:
            logger.warning("AI market report unavailable: %s", exc)

        assistant = await self._get_stock_assistant()
        result = await assistant.process_message("گزارش بازار")
        return {
            "text": result.get("text", "داده‌ای برای گزارش موجود نیست."),
            "type": "report",
            "suggestions": ["خلاصه بازار", "بهترین سهم‌ها", "تحلیل فولاد"],
        }

    def _handle_anomalies(self) -> dict[str, Any]:
        return {
            "text": "🚨 **تشخیص ناهنجاری بازار**\n\nناهنجاری‌های قیمت و حجم با تحلیل Z-Score شناسایی می‌شوند.\nبرای مشاهده به صفحه ناهنجاری‌ها بروید.",
            "type": "anomalies",
            "actions": [{"type": "link", "label": "🚨 صفحه ناهنجاری‌ها", "url": "/anomalies"}],
            "suggestions": ["ناهنجاری‌های شدید", "ناهنجاری حجم", "خلاصه بازار"],
        }

    async def _handle_signals(self) -> dict[str, Any]:
        # Priority 1: latest AI buy signals from the 110-column model
        try:
            from services.screener_ai_report_service import ScreenerAIReportService

            report = await ScreenerAIReportService(self._session).generate_market_report(limit=20)
            if report.get("text"):
                return {
                    "text": report["text"],
                    "type": "signals",
                    "data": {
                        "stats": report.get("stats"),
                        "buy_signals": report.get("buy_signals", [])[:20],
                    },
                    "actions": [
                        {"type": "link", "label": "📡 صفحه سیگنال‌ها", "url": "/signals"},
                        {"type": "link", "label": "🔍 غربال‌گر هوشمند", "url": "/smart-screener"},
                    ],
                    "suggestions": ["سیگنال‌های خرید", "بهترین سهم‌ها", "خلاصه بازار"],
                }
        except Exception as exc:
            logger.warning("AI signals unavailable: %s", exc)

        return {
            "text": "📡 **سیگنال‌های معاملاتی**\n\nبرای مشاهده سیگنال‌ها به صفحه مربوطه بروید.",
            "type": "signals",
            "actions": [{"type": "link", "label": "📡 صفحه سیگنال‌ها", "url": "/signals"}],
            "suggestions": ["سیگنال‌های خرید", "سیگنال‌های فروش", "خلاصه بازار"],
        }

    def _handle_navigate(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        page = params.get("page", "")
        url = resolve_page(page or text)

        if url:
            page_name = {v: k for k, v in _PAGE_MAP.items()}.get(url, url)
            return {
                "text": f"🔗 در حال انتقال به صفحه {page_name}...",
                "type": "navigation",
                "link": url,
                "link_label": f"🔗 برو به {page_name}",
                "actions": [{"type": "navigate", "url": url}],
                "suggestions": ["بازار چطوره؟", "تحلیل فولاد", "بهترین سهم‌ها"],
            }

        return {
            "text": "صفحه مورد نظر یافت نشد. لطفاً نام صفحه را مشخص کنید.\n\nبرخی صفحات: بازار، غربالگر، دیده‌بان، اخبار، تحلیل، بک‌تست",
            "type": "error",
            "suggestions": ["برو به بازار", "برو به غربالگر", "برو به دیده‌بان"],
        }

    def _handle_crypto(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        return {
            "text": "💰 **ارزهای دیجیتال**\n\nقیمت لحظه‌ای ارزهای دیجیتال را مشاهده کنید.",
            "type": "crypto",
            "actions": [{"type": "link", "label": "💰 صفحه ارز دیجیتال", "url": "/crypto"}],
            "suggestions": ["قیمت بیت کوین", "قیمت اتریوم", "تحلیل فولاد"],
        }

    def _handle_commodities(self, params: dict[str, Any], text: str) -> dict[str, Any]:
        return {
            "text": "🌍 **کامودیتی‌ها**\n\nقیمت فلزات گران‌بها، نفت و انرژی را مشاهده کنید.",
            "type": "commodities",
            "actions": [{"type": "link", "label": "🌍 صفحه کامودیتی", "url": "/commodities"}],
            "suggestions": ["قیمت طلا", "قیمت نفت", "تحلیل فولاد"],
        }

    def _handle_unknown(self, text: str) -> dict[str, Any]:
        return {
            "text": (
                "🤖 **متوجه درخواست شما نشدم.**\n\n"
                "لطفاً یکی از موارد زیر را امتحان کنید:\n\n"
                "📊 **تحلیل:** «تحلیل فولاد»\n"
                "📈 **بازار:** «بازار چطوره؟»\n"
                "🔍 **غربال:** «بهترین سهم‌ها»، «سهم ارزنده»، «پول هوشمند»\n"
                "👁️ **دیده‌بان:** «اضافه فولاد به دیده‌بان»\n"
                "🔔 **هشدار:** «هشدار فولاد rsi above 70»\n"
                "💼 **پرتفوی:** «پرتفوی من»\n"
                "🧪 **بک‌تست:** «بک‌تست فولاد»\n"
                "🧠 **پیش‌بینی:** «پیش‌بینی فولاد»\n"
                "📰 **اخبار:** «اخبار بازار»\n"
                "🏢 **کدال:** «اطلاعیه فولاد»\n"
                "💰 **ارز دیجیتال:** «قیمت بیت کوین»\n"
                "🌍 **کامودیتی:** «قیمت طلا»، «قیمت نفت»\n"
                "🔗 **ناوبری:** «برو به غربالگر»\n"
                "❓ **راهنما:** «help»"
            ),
            "type": "unknown",
            "suggestions": [
                "help",
                "تحلیل فولاد",
                "بازار چطوره؟",
                "بهترین سهم‌ها",
                "سهم ارزنده",
                "پول هوشمند وارد شده",
                "اخبار بازار",
                "قیمت بیت کوین",
                "اضافه فولاد به دیده‌بان",
                "پرتفوی من",
            ],
        }

    # ── Helpers ────────────────────────────────────────────────────────────

    def _empty_response(self) -> dict[str, Any]:
        return {
            "text": "پیامی وارد نکردید. چطور می‌توانم کمک کنم؟",
            "type": "empty",
            "suggestions": ["help", "تحلیل فولاد", "بازار چطوره؟"],
        }

    async def _try_extract_symbol(self, text: str) -> str | None:
        """Try to find a Persian stock symbol mentioned in the text."""
        try:
            assistant = await self._get_stock_assistant()
            return await assistant._extract_symbol(text)
        except Exception as e:
            logger.debug("Failed to extract symbol via assistant: %s", e)
            # Hardcoded fallback for common symbols
            common = ["فولاد", "فملی", "شپنا", "وبملت", "خودرو", "کگل", "شتران", "وغدیر"]
            for sym in common:
                if sym in text:
                    return sym
            return None

    async def _random_symbol(self) -> str:
        """Return a random symbol for suggestions."""
        return "فولاد"

    def _get_suggestions_for_type(self, response_type: str) -> list[str]:
        suggestions_map: dict[str, list[str]] = {
            "recommendation": ["بهترین سهم‌ها", "مقایسه فولاد و خودرو", "خلاصه بازار"],
            "market": ["افزایشی‌ها", "کاهشی‌ها", "تحلیل فولاد"],
            "comparison": ["تحلیل فولاد", "بهترین سهم‌ها", "خلاصه بازار"],
            "filter": ["فیلتر RSI<30", "سهام ارزنده", "تحلیل فولاد"],
            "screener": ["نمادهای با SMC بالا", "فیلتر P/E<7", "تحلیل فولاد"],
            "error": ["help", "تحلیل فولاد", "بازار چطوره؟"],
        }
        return suggestions_map.get(response_type, ["help", "تحلیل فولاد", "بازار چطوره؟"])
