"""IntentClassifier — ML-based intent detection with regex fallback (Level 7).

Supports both:
- ML-based classification (TF-IDF + LogisticRegression via sklearn)
- Regex pattern matching (fallback when sklearn unavailable)

Covers ALL intents across the 20-level architecture.
"""

from __future__ import annotations

import re

from core.logging import get_logger

logger = get_logger(__name__)

# ── Intent Definitions ──────────────────────────────────────────────

INTENTS = [
    "greeting",
    "farewell",
    "help",
    "analyze_symbol",
    "analyze_all",
    "compare_symbols",
    "market_overview",
    "top_gainers",
    "top_losers",
    "find_cheap",
    "find_best",
    "screener",
    "dynamic_filter",
    "add_watchlist",
    "remove_watchlist",
    "list_watchlist",
    "add_alert",
    "list_alerts",
    "remove_alert",
    "portfolio_add",
    "portfolio_remove",
    "portfolio_summary",
    "run_backtest",
    "list_backtests",
    "ml_predict",
    "ml_train",
    "ml_list_models",
    "get_news",
    "get_codal",
    "macro_data",
    "gold_currency",
    "crypto_prices",
    "heatmap",
    "risk_overview",
    "signals",
    "anomalies",
    "navigate",
    "recommendation",
    "get_chart",
    "speech_input",
    "personalize",
    "complex_mixed",
    "unknown",
]

# Full regex pattern map for ALL intents
INTENT_PATTERNS: dict[str, list[str]] = {
    "greeting": [
        r"^(سلام|درود|هلو|اسلام|های|هی|خوبی|حالت|چطوری|چخبر|چه خبر|احوال)",
        r"^(صبح|بعد از ظهر|عصر)\s*(به خیر|بخیر)",
        r"^(hi|hello|hey|good morning|good evening)",
    ],
    "farewell": [
        r"(خداحافظ|خدانگهدار|فعلا|بای|تا بعد|تا بعد|برم|من رفتم)",
        r"(bye|goodbye|see you|see ya|cya)",
    ],
    "help": [
        r"(کمک|راهنما|help|دستورات|چیکار|توانایی|امکانات|چه کار می‌تونی|چیکار بلدی)",
        r"(capabilities|what can you|commands|how to)",
    ],
    "analyze_symbol": [
        r"(تحلیل\s*کن|بررسی\s*کن|بررسیش|وضعیت|چطوره|حالش\s*چطوره|چه حالی داره)",
        r"(ارزش خرید|می‌ارزه|بخرم|بفروشم|نگهش دارم)",
        r"(آیا\s*(خوبه|مناسبه|می‌ارزه))",
        r"(تحلیل|بررسی)\s*(کامل|فنی|تکنیکال|بنیادی)?\s*(\S+)",
        r"(\S+)\s*(چطوره|تحلیل|بررسی|وضعیت)",
    ],
    "analyze_all": [
        r"(تحلیل\s*همه|همه\s*سهم|بررسی\s*همه|تحلیل\s*تمام)",
        r"(all\s*stocks|analyze\s*all|market\s*wide)",
    ],
    "compare_symbols": [
        r"مقایسه\s*(\S+)\s*(و|با)\s*(\S+)",
        r"(\S+)\s*(مقایسه|با)\s*(\S+)",
        r"(کدوم\s*بهتره|تفاوت)\s*(\S+)\s*(و|با)\s*(\S+)",
        r"(compare|comparison)\s*(\S+)\s*(and|vs|with)\s*(\S+)",
    ],
    "market_overview": [
        r"(خلاصه|بازار)\s*(بازار|امروز|خلاصه)",
        r"بازار\s*(چطوره|چته|چه خبر|سبزه|قرمزه|چطوری)",
        r"(شاخص\s*کل|شاخص\s*بورس|شاخص\s*فرابورس)",
        r"(market\s*overview|market\s*summary|market\s*today)",
    ],
    "top_gainers": [
        r"(بیشترین|بالاترین|برترین)\s*(افزایش|رشد|مثبت|سود|بازده)",
        r"(top\s*gainer|best\s*performer|highest\s*return)",
        r"پرمتقاضی|پرمتحرک\s*مثبت",
    ],
    "top_losers": [
        r"(بیشترین|پایین‌ترین)\s*(کاهش|افت|منفی|ضرر|زیان)",
        r"(top\s*loser|worst\s*performer|biggest\s*drop)",
        r"پرمتحرک\s*منفی",
    ],
    "find_cheap": [
        r"(سهام\s*ارزنده|ارزان|ارزون|ارزون‌ترین|ارزنده)",
        r"(cheap\s*stock|undervalued|value\s*stock|low\s*pe)",
    ],
    "find_best": [
        r"(بهترین|برترین|گلچین|سهم\s*خوب|سهام\s*خوب|چه\s*سهمی\s*بخرم)",
        r"(پیشنهاد\s*(سهم|بده|کن|میدی)|سهم\s*پیشنهادی)",
        r"(best\s*stock|top\s*pick|recommended\s*stock|hot\s*stock)",
        r"سهم\s*های\s*(خوب|برتر|ارزنده|پرحجم|پرتقاضا)",
        r"کدوم\s*(سهم|نماد)\s*(خوب|بهتر|ارزنده)",
    ],
    "screener": [
        r"(غربال|screener|screen)\s*(کن|گری|گر)?",
        r"(پول\s*هوشمند|smart\s*money|smc)",
        r"(حجم\s*(بالا|زیاد|سنگین)|تجمع|توزیع)",
        r"(شکست\s*(مقاومت|حمایت|روند)|breakout)",
        r"(سیگنال\s*(خرید|فروش|صعودی|نزولی))",
        r"(میانگین\s*(متحرک|ساده)\s*(رو|بر)?\s*(\d+))",
        r"(نهادی\s*(خرید|فروش|ورود|خروج)|حقیقی\s*(خرید|فروش))",
    ],
    "dynamic_filter": [
        r"فیلتر\s+(RSI|P/E|ROE|حجم|volume|قیمت|price|SMC|smc|نقدشوندگی|liquidity|قدرت|power)\s*([<>=!]+\s*[\d.]+)",
        r"(filter|screening)\s*(by|with|for)\s*(rsi|pe|roe|volume|price|smc|liquidity)",
        r"(RSI|P/E|ROE)\s*(<=|>=|<|>)\s*(\d+)",
    ],
    "get_news": [
        r"(اخبار|news|خبر|اخبار|آخرین\s*اخبار|خبرای|خبرای)",
        r"(اخبار\s*(فولاد|شبندر|خودرو|خساپا|شپنا|فملی|کگل|وغدیر))",
        r"(چه\s*خبر|تازه\s*ها|آخرین\s*خبرها)",
    ],
    "get_codal": [
        r"(کدال|codal|اطلاعیه|گزارش\s*مالی|صورت\s*مالی)",
        r"(افزایش\s*سرمایه|مجمع|سود\s*(تقسیم|نقدی)|EPS)",
    ],
    "macro_data": [
        r"(ماکرو|macro|اقتصاد|اقتصادی|تورم|gdp|نرخ\s*بهره)",
        r"(سانا|نیمایی|آزاد|رسمی)",
        r"(قیمت\s*(جهانی|بین‌المللی|کالا))",
    ],
    "gold_currency": [
        r"(طلا|gold|سکه|دلار|ارز|currency|dollar|یورو|پوند|نرخ)",
        r"(انس\s*(طلا|نقره|پلاتین)|نفت|برنت|WTI)",
        r"(قیمت\s*(دلار|طلا|سکه|ارز|یورو|پوند))",
        r"(نرخ\s*(دلار|ارز|طلا|سکه))",
    ],
    "crypto_prices": [
        r"(رمزارز|ارز\s*دیجیتال|کریپتو|crypto|bitcoin|اتریوم|بیت\s*کوین|تتر|BNB|SOL|XRP)",
        r"(قیمت\s*(بیت\s*کوین|اتریوم|تتر|BTC|ETH|USDT))",
    ],
    "add_watchlist": [
        r"(اضافه|افزودن|بذار|بزار)\s*(به|تو)?\s*(دیده‌بان|لیست|پیگیری|دنبال|watchlist|watch|follow)",
        r"(add|follow)\s*(to)?\s*(watchlist|watch|list)",
    ],
    "remove_watchlist": [
        r"(حذف|پاک|بردار)\s*(از)?\s*(دیده‌بان|لیست|پیگیری|watchlist|watch)",
        r"(remove|delete|unfollow)\s*(from)?\s*(watchlist|watch)",
    ],
    "list_watchlist": [
        r"(دیده‌بان|watchlist|لیست\s*پیگیری|دنبالی\s*ها|my\s*list)",
        r"(نمایش|لیست|مشاهده)\s*(دیده‌بان|پیگیری|دنبالی)",
    ],
    "add_alert": [
        r"هشدار\s*(اضافه|جدید|ثبت|بزن|بگذار|بذار)",
        r"(alert|alarm)\s*(add|new|create|set)",
        r"هشدار\s*(\S+)\s*(rsi|price|قیمت|حجم|volume)\s*(بالاتر|پایین‌تر|above|below)\s*(\d+)",
    ],
    "list_alerts": [
        r"(لیست|نمایش|مشاهده)\s*(هشدار|alert|alarm)",
        r"هشدارهای\s*(فعال|من|موجود)",
        r"(alerts?)\s*(list|active|all|show)",
    ],
    "remove_alert": [
        r"(حذف|پاک|غیرفعال)\s*(کردن)?\s*(هشدار|alert)",
        r"(remove|delete|clear)\s*(alert|alarm)",
    ],
    "portfolio_add": [
        r"(اضافه|خرید|افزودن|add|buy)\s*(\S+)\s*(\d+)\s*(سهم)?\s*(به\s*قیمت|با\s*قیمت|at)?\s*(\d+)",
    ],
    "portfolio_remove": [
        r"(حذف|فروش|remove|sell)\s*(\S+)\s*(از)?\s*(پرتفوی|سبد|portfolio)?",
    ],
    "portfolio_summary": [
        r"(خلاصه|وضعیت|نمایش|show|summary)\s*(پرتفوی|سبد|portfolio)",
        r"(پرتفوی|سبد)\s*(من|خلاصه|وضعیت|چطوره)",
        r"(سود|زیان|سود و زیان)\s*(پرتفوی|سبد)?",
    ],
    "run_backtest": [
        r"(بک‌تست|backtest|آزمون)\s*(\S+)?",
        r"(اجرا|run|execute)\s*(بک‌تست|backtest)",
    ],
    "list_backtests": [
        r"(بک‌تست|backtest)\s*(های|ها)\s*(قبلی|من|ذخیره|list)",
        r"(لیست|تاریخچه|history)\s*(بک‌تست|backtest)",
    ],
    "ml_predict": [
        r"(پیش‌بینی|predict|forecast|پیشبینی)\s*(\S+)?",
        r"(مدل|model|ml)\s*(پیش‌بینی|predict|پیشگویی)",
    ],
    "ml_train": [
        r"(آموزش|train|training)\s*(مدل|model)",
        r"train-all|train_all|train all|retrain",
    ],
    "ml_list_models": [
        r"(مدل|model|ml)\s*(ها|هامو|list|لیست|موجود)",
        r"(list|نمایش|مشاهده)\s*(مدل|model)",
    ],
    "heatmap": [
        r"(نقشه|heatmap|map)\s*(بازار|market|حرارتی)?",
        r"(نقشه\s*حرارتی|نقشه\s*بازار|نقشه\s*رنگ)",
    ],
    "risk_overview": [
        r"(ریسک|risk|var|cvar|شارپ|sharp|drawdown)",
        r"(مدیریت\s*ریسک|risk\s*management|risk\s*metrics)",
    ],
    "signals": [
        r"(سیگنال|signal)\s*(خرید|فروش|معاملاتی|ها)?",
        r"سیگنال‌های\s*(جدید|فعال|امروز)",
    ],
    "anomalies": [
        r"(ناهنجاری|anomaly|anomal|غیرعادی|spike|جهش\s*قیمت|حجم\s*غیرعادی)",
        r"(abnormal|outlier|unusual|exceptional)",
    ],
    "navigate": [
        r"(برو\s*به|بریم|رفتن|open|باز|نمایش|مشاهده)\s*(\S+)",
        r"صفحه\s*(\S+)\s*(رو|را)?\s*(باز|نشون|ببین|نشان)",
        r"(go\s*to|open|show|navigate)\s*(page|screen|section)?\s*(\S+)",
    ],
    "get_chart": [
        r"(نمودار|chart|graph|plot|رسم|کشیدن)\s*(\S+)?",
        r"(نمودار\s*(قیمت|حجم|اندیکاتور|rsi|macd))",
    ],
    "speech_input": [
        r"(صوتی|voice|speech|گفتار|ضبط|صحبت)",
        r"(بگو|بخوان|تلفظ)",
    ],
    "personalize": [
        r"(شخصی|personalize|personalization|تنظیمات|پروفایل|profile)",
        r"(علاقه|علایق|دنبال|محبوب|favorite|fav)",
    ],
    "complex_mixed": [
        r"(\S+)\s*(و)\s*(\S+)\s*(و)\s*(\S+)\s*(با)\s*(\S+)",
        r"(\S+)\s*(مقایسه|تحلیل)\s*(\S+)\s*(اخبار|نمودار|سیگنال)",
        r"(ترکیب|mixed|complex|چند\s*عملیاتی)",
    ],
    "recommendation": [
        r"(پیشنهاد\s*(می‌کنی|میدی|بده|کن)|چی\s*(پیشنهاد|خرید|بگم))",
        r"(recommend|suggestion|advise|opinion)",
        r"(به\s*نظرت|فکر\s*می‌کنی|به\s*چه\s*سهمی)",
    ],
}


class IntentClassifier:
    """ML-based intent classifier with regex fallback.

    Uses TF-IDF + LogisticRegression when sklearn is available,
    falls back to regex pattern matching for Persian/English queries.
    """

    def __init__(self):
        self._model = None
        self._vectorizer = None
        self._is_ml_ready = False
        self._try_load_ml()

    def _try_load_ml(self) -> None:
        """Attempt to load sklearn for ML-based classification."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression

            self._TfidfVectorizer = TfidfVectorizer
            self._LogisticRegression = LogisticRegression
            self._is_ml_ready = True
        except ImportError:
            logger.info("sklearn not available — using regex-based intent classification")
            self._is_ml_ready = False

    def train(self, texts: list[str], intents: list[str]) -> None:
        """Train ML model with sample texts and intents."""
        if not self._is_ml_ready or not texts:
            return

        try:
            self._vectorizer = self._TfidfVectorizer(max_features=5000, ngram_range=(1, 3))
            X = self._vectorizer.fit_transform(texts)
            self._model = self._LogisticRegression(max_iter=1000, multi_class="multinomial")
            self._model.fit(X, intents)
            logger.info("Intent classifier trained on %d samples", len(texts))
        except Exception as e:
            logger.warning("ML training failed: %s — falling back to regex", e)
            self._is_ml_ready = False

    def predict(self, text: str) -> tuple[str, float]:
        """Predict intent from text. Returns (intent_name, confidence)."""
        text = text.strip()
        if not text:
            return "unknown", 0.0

        # 1. Try ML first (if available and trained)
        ml_intent, ml_confidence = self._predict_ml(text)
        if ml_intent and ml_confidence > 0.6:
            return ml_intent, ml_confidence

        # 2. Try regex patterns
        regex_intent, regex_confidence = self._predict_regex(text)
        if regex_intent and regex_confidence > 0.0:
            return regex_intent, regex_confidence

        # 3. Fallback: use regex with lower threshold
        if regex_intent:
            return regex_intent, regex_confidence

        return "unknown", 0.0

    def _predict_ml(self, text: str) -> tuple[str | None, float]:
        """Predict using ML model."""
        if not self._model or not self._vectorizer:
            return None, 0.0
        try:
            X = self._vectorizer.transform([text])
            pred = self._model.predict(X)[0]
            proba = self._model.predict_proba(X).max()
            return pred, float(proba)
        except Exception:
            return None, 0.0

    def _predict_regex(self, text: str) -> tuple[str | None, float]:
        """Predict using regex pattern matching."""
        text_lower = text.lower().strip()

        best_intent = None
        best_score = 0.0

        for intent, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Calculate confidence based on match quality
                    matched_text = match.group()
                    coverage = len(matched_text) / max(len(text_lower), 1)
                    position_bonus = 0.2 if match.start() == 0 else 0.0
                    confidence = min(1.0, coverage * 0.8 + position_bonus)

                    if confidence > best_score:
                        best_score = confidence
                        best_intent = intent

                    # Early exit for very high confidence
                    if confidence > 0.9:
                        return intent, confidence

        return best_intent, best_score

    def predict_multi(self, text: str, threshold: float = 0.2) -> list[tuple[str, float]]:
        """Predict multiple possible intents above threshold."""
        results: list[tuple[str, float]] = []

        # Check all regex patterns
        text_lower = text.lower().strip()
        for intent, patterns in INTENT_PATTERNS.items():
            best_for_intent = 0.0
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    coverage = len(match.group()) / max(len(text_lower), 1)
                    position_bonus = 0.2 if match.start() == 0 else 0.0
                    confidence = min(1.0, coverage * 0.8 + position_bonus)
                    best_for_intent = max(best_for_intent, confidence)

            if best_for_intent >= threshold:
                results.append((intent, best_for_intent))

        results.sort(key=lambda x: x[1], reverse=True)
        return results


# ── Default training data ───────────────────────────────────────────

DEFAULT_TRAINING_DATA: list[tuple[str, str]] = [
    # Greetings
    ("سلام", "greeting"),
    ("درود بر شما", "greeting"),
    ("سلام خوبی", "greeting"),
    ("hello", "greeting"),
    ("hi", "greeting"),
    ("صبح بخیر", "greeting"),
    ("عصر بخیر", "greeting"),
    ("چطوری", "greeting"),
    ("حالت خوبه", "greeting"),
    ("چه خبر", "greeting"),

    # Farewell
    ("خداحافظ", "farewell"),
    ("فعلا", "farewell"),
    ("بای بای", "farewell"),
    ("تا بعد", "farewell"),
    ("bye", "farewell"),
    ("goodbye", "farewell"),

    # Help
    ("help", "help"),
    ("راهنما", "help"),
    ("چه کمکی می‌تونی بکنی", "help"),
    ("چیکار می‌تونی", "help"),
    ("دستورات", "help"),
    ("امکانات", "help"),

    # Analysis
    ("فولاد رو تحلیل کن", "analyze_symbol"),
    ("تحلیل فولاد", "analyze_symbol"),
    ("وضعیت فولاد چطوره", "analyze_symbol"),
    ("فولاد چطوره", "analyze_symbol"),
    ("ارزش خرید داره فولاد", "analyze_symbol"),
    ("آیا فولاد خوبه", "analyze_symbol"),
    ("فولاد می‌ارزه بخرم", "analyze_symbol"),
    ("شبندر رو بررسی کن", "analyze_symbol"),
    ("وضعیت خودرو چطوره", "analyze_symbol"),
    ("تحلیل کامل شپنا", "analyze_symbol"),
    ("خودرو رو تحلیل کن", "analyze_symbol"),

    # Compare
    ("فولاد و خودرو مقایسه", "compare_symbols"),
    ("مقایسه فولاد و شپنا", "compare_symbols"),
    ("کدوم بهتره فولاد یا خودرو", "compare_symbols"),
    ("compare foolad and khodro", "compare_symbols"),
    ("تفاوت فولاد و شبندر", "compare_symbols"),

    # Market
    ("بازار چطوره", "market_overview"),
    ("خلاصه بازار", "market_overview"),
    ("بازار امروز چطوره", "market_overview"),
    ("شاخص کل", "market_overview"),
    ("market summary", "market_overview"),
    ("بازار سبزه", "market_overview"),
    ("بازار قرمزه", "market_overview"),

    # Best stocks
    ("بهترین سهم‌ها", "find_best"),
    ("بهترین سهام", "find_best"),
    ("سهم خوب", "find_best"),
    ("سهام خوب", "find_best"),
    ("چه سهمی بخرم", "find_best"),
    ("پیشنهاد سهم", "find_best"),
    ("گلچین", "find_best"),
    ("top stocks", "find_best"),

    # Cheap stocks
    ("سهام ارزنده", "find_cheap"),
    ("سهام ارزان", "find_cheap"),
    ("ارزونه", "find_cheap"),
    ("undervalued stocks", "find_cheap"),

    # News
    ("اخبار فولاد", "get_news"),
    ("آخرین اخبار بازار", "get_news"),
    ("اخبار مهم امروز", "get_news"),
    ("خبرهای بازار", "get_news"),
    ("چه خبرا", "get_news"),
    ("news", "get_news"),

    # Codal
    ("اطلاعیه فولاد", "get_codal"),
    ("کدال", "get_codal"),
    ("گزارش مالی فولاد", "get_codal"),
    ("افزایش سرمایه فولاد", "get_codal"),

    # Gold & Currency
    ("قیمت طلا", "gold_currency"),
    ("قیمت دلار", "gold_currency"),
    ("طلا و سکه", "gold_currency"),
    ("نرخ ارز", "gold_currency"),
    ("دلار چند", "gold_currency"),
    ("gold price", "gold_currency"),

    # Crypto
    ("قیمت بیت کوین", "crypto_prices"),
    ("bitcoin price", "crypto_prices"),
    ("ارز دیجیتال", "crypto_prices"),
    ("اتریوم", "crypto_prices"),

    # Watchlist
    ("فولاد به دیده‌بان", "add_watchlist"),
    ("اضافه فولاد به دیده‌بان", "add_watchlist"),
    ("دیده‌بان من", "list_watchlist"),
    ("نمایش دیده‌بان", "list_watchlist"),
    ("حذف فولاد از دیده‌بان", "remove_watchlist"),
    ("add to watchlist", "add_watchlist"),

    # Alerts
    ("هشدار فولاد rsi above 70", "add_alert"),
    ("هشدار new فولاد", "add_alert"),
    ("لیست هشدارها", "list_alerts"),
    ("هشدارهای فعال", "list_alerts"),
    ("حذف هشدار فولاد", "remove_alert"),

    # Portfolio
    ("خرید فولاد ۱۰۰", "portfolio_add"),
    ("پرتفوی من", "portfolio_summary"),
    ("خلاصه پرتفوی", "portfolio_summary"),
    ("وضعیت سبد", "portfolio_summary"),
    ("فروش فولاد", "portfolio_remove"),

    # Filter
    ("فیلتر RSI<30", "dynamic_filter"),
    ("فیلتر P/E<8 ROE>20", "dynamic_filter"),
    ("filter rsi below 30", "dynamic_filter"),
    ("غربالگری کن", "screener"),
    ("smart money", "screener"),
    ("پول هوشمند", "screener"),
    ("SMC بالا", "screener"),

    # Macro
    ("تورم", "macro_data"),
    ("نرخ بهره", "macro_data"),
    ("GDP", "macro_data"),
    ("اقتصاد ایران", "macro_data"),
    ("ماکرو", "macro_data"),

    # ML
    ("پیش‌بینی فولاد", "ml_predict"),
    ("predict foolad", "ml_predict"),
    ("پیشبینی قیمت", "ml_predict"),
    ("آموزش مدل", "ml_train"),
    ("مدل‌ها رو ببین", "ml_list_models"),

    # Backtest
    ("بک‌تست فولاد", "run_backtest"),
    ("backtest foolad", "run_backtest"),
    ("لیست بک‌تست‌ها", "list_backtests"),

    # Charts
    ("نمودار فولاد", "get_chart"),
    ("نمودار قیمت", "get_chart"),
    ("چارت فولاد", "get_chart"),
    ("رسم نمودار فولاد", "get_chart"),

    # Heatmap
    ("نقشه بازار", "heatmap"),
    ("نقشه حرارتی", "heatmap"),
    ("heatmap", "heatmap"),

    # Risk
    ("ریسک", "risk_overview"),
    ("مدیریت ریسک", "risk_overview"),
    ("شاخص ریسک", "risk_overview"),

    # Signals
    ("سیگنال خرید", "signals"),
    ("سیگنال فروش", "signals"),
    ("سیگنال‌ها", "signals"),

    # Anomalies
    ("ناهنجاری", "anomalies"),
    ("ناهنجاری قیمت", "anomalies"),
    ("حجم غیرعادی", "anomalies"),

    # Navigation
    ("برو به بازار", "navigate"),
    ("برو به غربالگر", "navigate"),
    ("go to screener", "navigate"),
    ("صفحه تحلیل", "navigate"),
    ("برو به پرتفوی", "navigate"),

    # Gainers & Losers
    ("پرمتقاضی‌ترین", "top_gainers"),
    ("بیشترین رشد", "top_gainers"),
    ("top gainers", "top_gainers"),
    ("بیشترین کاهش", "top_losers"),
    ("top losers", "top_losers"),

    # Analyze all
    ("تحلیل همه سهم‌ها", "analyze_all"),
    ("همه سهم‌ها رو تحلیل کن", "analyze_all"),

    # Complex
    ("تحلیل فولاد و مقایسه با شپنا", "complex_mixed"),
    ("قیمت و اخبار فولاد", "complex_mixed"),
    ("فولاد رو تحلیل کن و جمع اخبارش رو بده", "complex_mixed"),

    # Personalization
    ("علاقه‌مندی‌های من", "personalize"),
    ("پروفایل من", "personalize"),
    ("symbols مورد علاقه", "personalize"),
]
