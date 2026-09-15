"""NewsAnalyzer — Analyze and summarize Persian financial news (Level 16).

Provides:
- Sentiment analysis for Persian financial news
- Key event detection (capital increase, dividend, etc.)
- News summarization
- Impact scoring for market relevance
"""

from __future__ import annotations

from typing import Any


class NewsAnalyzer:
    """Analyze Persian financial news for sentiment, events, and impact."""

    # Keywords with impact weights (higher = more impactful)
    IMPORTANT_KEYWORDS: dict[str, int] = {
        "افزایش سرمایه": 3,
        "تقسیم سود": 3,
        "اختصاصی": 1,
        "مجمع": 2,
        "گزارش مالی": 2,
        "سودآوری": 2,
        "سود نقدی": 3,
        "EPS": 2,
        "DPS": 3,
        "تغییر مدیریت": 2,
        "مدیرعامل": 2,
        "هیئت مدیره": 1,
        "خرید سهام": 2,
        "فروش سهام": 2,
        "پالایش": 1,
        "تولید": 1,
        "صادرات": 1,
        "واردات": 1,
        "تورم": 1,
        "نرخ ارز": 2,
        "تحریم": 3,
        "توافق": 3,
        "برجام": 3,
        "دولت": 1,
        "مجلس": 1,
        "قیمت گذاری": 1,
        "نرخ گذاری": 1,
        "افزایش قیمت": 2,
        "کاهش قیمت": 2,
        "رشد تولید": 2,
        "کاهش تولید": 2,
        "شفاف سازی": 1,
        "پیش بینی": 1,
        "سود هر سهم": 2,
        "سرمایه گذاری": 1,
        "طرح توسعه": 2,
        "خرید داریی": 1,
        "فروش دارایی": 1,
    }

    # Positive sentiment words
    POSITIVE_WORDS: set[str] = {
        "افزایش",
        "رشد",
        "سود",
        "خرید",
        "توافق",
        "مثبت",
        "بهبود",
        "صعود",
        "جهش",
        "توسعه",
        "گسترش",
        "پیشرفت",
        "موفقیت",
        "سبز",
        "بالا",
        "قوی",
        "عالی",
        "خوب",
        "مناسب",
        "سودده",
        "سودآور",
        "بازده",
        "بهبودی",
        "رونق",
        "انعقاد",
        "امضا",
        "قرارداد",
        "همکاری",
        "افزایشی",
        "بهینه",
    }

    # Negative sentiment words
    NEGATIVE_WORDS: set[str] = {
        "کاهش",
        "افت",
        "ضرر",
        "فروش",
        "تحریم",
        "منفی",
        "ریزش",
        "نگرانی",
        "بحران",
        "مشکل",
        "اخطار",
        "هشدار",
        "زیان",
        "نزول",
        "سقوط",
        "ضعیف",
        "بد",
        "نامناسب",
        "پایین",
        "قرمز",
        "کمبود",
        "محدودیت",
        "فشار",
        "توقف",
        "تعلیق",
        "ورشکستگی",
        "تعدیل",
        "بدهی",
        "زیانده",
        "اخلال",
        "تنش",
        "تحریمی",
        "کاهشی",
        "نگران کننده",
    }

    @classmethod
    def analyze(cls, news_list: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze a list of news items.

        Returns dict with:
        - has_news: bool
        - summary: str
        - sentiment: str (positive/negative/neutral)
        - sentiment_score: float (-1 to 1)
        - important_events: list[str]
        - top_headlines: list[str]
        - impact_score: float (0-1)
        - total_news: int
        """
        if not news_list:
            return {
                "has_news": False,
                "summary": "هیچ خبری یافت نشد.",
                "sentiment": "neutral",
                "sentiment_score": 0.0,
                "important_events": [],
                "top_headlines": [],
                "impact_score": 0.0,
                "total_news": 0,
            }

        # Extract headlines
        headlines = [n.get("title", "") for n in news_list[:5]]

        # Detect important events
        events = cls._extract_important_events(news_list)

        # Analyze sentiment
        sentiment, sentiment_score = cls._analyze_sentiment(news_list)

        # Calculate impact
        impact = cls._calculate_impact(news_list, events)

        # Generate summary
        summary = cls._generate_summary(news_list, events, sentiment)

        return {
            "has_news": True,
            "summary": summary,
            "sentiment": sentiment,
            "sentiment_score": round(sentiment_score, 3),
            "important_events": events[:5],
            "top_headlines": headlines,
            "impact_score": round(impact, 3),
            "total_news": len(news_list),
        }

    @classmethod
    def _extract_important_events(cls, news_list: list[dict]) -> list[str]:
        """Extract important financial events from news."""
        events = []
        seen = set()

        for news in news_list:
            text = f"{news.get('title', '')} {news.get('summary', '')}"

            for keyword, importance in cls.IMPORTANT_KEYWORDS.items():
                if keyword in text and keyword not in seen:
                    seen.add(keyword)
                    title_snippet = news.get("title", "")[:60]
                    if importance >= 2:
                        events.append(f"📌 {keyword}: {title_snippet}...")
                    else:
                        events.append(f"• {keyword}")

        return events

    @classmethod
    def _analyze_sentiment(cls, news_list: list[dict]) -> tuple[str, float]:
        """Analyze overall sentiment of news list.

        Returns (sentiment_label, sentiment_score) where score is -1 to 1.
        """
        pos_count = 0
        neg_count = 0

        for news in news_list:
            text = f"{news.get('title', '')} {news.get('summary', '')}"

            # Count positive/negative words with context
            for word in cls.POSITIVE_WORDS:
                if word in text:
                    # Check if negated
                    negated = cls._is_negated(text, word)
                    pos_count += -1 if negated else 1

            for word in cls.NEGATIVE_WORDS:
                if word in text:
                    negated = cls._is_negated(text, word)
                    neg_count += -1 if negated else 1

        total = pos_count + neg_count
        if total == 0:
            return "neutral", 0.0

        score = (pos_count - neg_count) / max(total, 1)
        score = max(-1.0, min(1.0, score))

        if score > 0.3:
            return "positive", score
        elif score < -0.3:
            return "negative", score
        else:
            return "neutral", score

    @staticmethod
    def _is_negated(text: str, word: str) -> bool:
        """Check if a word is negated in text."""
        idx = text.find(word)
        if idx < 0:
            return False

        before = text[max(0, idx - 20) : idx]
        negation_words = ["عدم", "غیر", "نه", "نبود", "ندارد", "نمی", "نیست", "بدون"]
        return any(nw in before for nw in negation_words)

    @classmethod
    def _calculate_impact(cls, news_list: list[dict], events: list[str]) -> float:
        """Calculate market impact score (0-1) based on news."""
        if not news_list:
            return 0.0

        # Factor 1: Number of news
        news_factor = min(1.0, len(news_list) / 10.0)

        # Factor 2: Important events
        event_factor = min(1.0, len(events) / 3.0)

        # Factor 3: Sentiment intensity
        _, sentiment_score = cls._analyze_sentiment(news_list)
        sentiment_factor = abs(sentiment_score)

        # Factor 4: Source diversity
        sources = {n.get("source") for n in news_list if n.get("source")}
        source_factor = min(1.0, len(sources) / 3.0)

        # Weighted combination
        impact = 0.25 * news_factor + 0.30 * event_factor + 0.25 * sentiment_factor + 0.20 * source_factor

        return min(1.0, impact)

    @classmethod
    def _generate_summary(cls, news_list: list[dict], events: list[str], sentiment: str) -> str:
        """Generate a concise Persian summary of news."""
        if not news_list:
            return ""

        latest = news_list[0]
        latest_title = latest.get("title", "")
        latest_source = latest.get("source", "")

        lines = [f"📰 آخرین خبر ({latest_source}): {latest_title}"]

        if events:
            top_events = events[:3]
            lines.append(f"\n🔹 رویدادهای مهم: {', '.join(top_events)}")

        sentiment_map = {
            "positive": "🟢 جو مثبت",
            "negative": "🔴 جو منفی",
            "neutral": "⚪ جو خنثی",
        }
        lines.append(f"\n📊 جو خبری: {sentiment_map.get(sentiment, 'نامشخص')}")

        if len(news_list) > 1:
            lines.append(f"\n📊 تعداد اخبار بررسی‌شده: {len(news_list)}")

        return "\n".join(lines)

    @classmethod
    def format_news_response(cls, symbol: str, analysis: dict[str, Any]) -> str:
        """Format news analysis as a Persian response string."""
        if not analysis.get("has_news"):
            return f"📭 خبری برای نماد {symbol} در روزهای اخیر یافت نشد."

        lines = [f"📰 **اخبار مرتبط با {symbol}:**", ""]
        lines.append(analysis.get("summary", ""))
        lines.append("")

        if analysis.get("top_headlines"):
            lines.append("**تیترهای مهم:**")
            for headline in analysis["top_headlines"][:3]:
                lines.append(f"  • {headline}")
            lines.append("")

        sentiment_map = {
            "positive": "🟢 مثبت",
            "negative": "🔴 منفی",
            "neutral": "⚪ خنثی",
        }
        lines.append(f"📊 **جو خبری:** {sentiment_map.get(analysis['sentiment'], 'نامشخص')}")
        lines.append(f"📊 **تعداد اخبار:** {analysis.get('total_news', 0)}")

        return "\n".join(lines)
