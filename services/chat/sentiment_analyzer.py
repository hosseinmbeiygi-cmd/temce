"""SentimentAnalyzer — Persian financial sentiment analysis (Level 14).

Provides:
- Keyword-based sentiment for Persian financial text
- Market sentiment aggregation
- Sentiment trend detection
- Social media / news sentiment fusion
"""

from __future__ import annotations

import re
from typing import Any


class SentimentAnalyzer:
    """Analyze sentiment in Persian financial text."""

    # Positive financial words with weights
    POSITIVE_WEIGHTS: dict[str, float] = {
        "افزایش": 0.6, "رشد": 0.7, "جهش": 0.9, "صعود": 0.8,
        "سود": 0.5, "سودآوری": 0.7, "سودده": 0.6,
        "خرید": 0.4, "تقاضا": 0.5, "خریدار": 0.3,
        "توافق": 0.8, "تفاهم": 0.6, "قرارداد": 0.5,
        "توسعه": 0.5, "گسترش": 0.5, "پیشرفت": 0.6,
        "بهبود": 0.6, "بهبودی": 0.6, "بهترین": 0.4,
        "قوی": 0.5, "عالی": 0.7, "مناسب": 0.3,
        "بازده": 0.5, "سوددهی": 0.6, "سودآور": 0.7,
        "افزایشی": 0.4, "مثبت": 0.5, "سبز": 0.4,
        "رونق": 0.6, "امیدوار": 0.4,
        "پایدار": 0.3, "مطمئن": 0.3, "اعتماد": 0.4,
        "ثبات": 0.3, "آرامش": 0.2, "حمایت": 0.4,
        "اعتبار": 0.3, "شفاف": 0.3, "تأیید": 0.4,
        "موفق": 0.6, "موفقیت": 0.7, "برنده": 0.5,
    }

    # Negative financial words with weights
    NEGATIVE_WEIGHTS: dict[str, float] = {
        "کاهش": 0.6, "افت": 0.7, "ریزش": 0.9, "سقوط": 0.9,
        "ضرر": 0.6, "زیان": 0.6, "زیانده": 0.7,
        "فروش": 0.4, "عرضه": 0.3, "فروشنده": 0.3,
        "تحریم": 0.9, "تحریمی": 0.8, "تنش": 0.6,
        "بحران": 0.8, "مشکل": 0.5, "اخطار": 0.6, "هشدار": 0.5,
        "نزول": 0.7, "ضعیف": 0.5, "نامناسب": 0.4,
        "پایین": 0.3, "قرمز": 0.3, "کمبود": 0.4,
        "توقف": 0.6, "تعلیق": 0.7, "ورشکستگی": 0.9,
        "بدهی": 0.5, "اخلال": 0.5, "نگران": 0.6,
        "نگرانی": 0.6, "نگران کننده": 0.7,
        "فشار": 0.4, "محدودیت": 0.4, "ممنوعیت": 0.6,
        "ترس": 0.5, "وحشت": 0.8, "شکست": 0.6,
        "کاهشی": 0.5, "منفی": 0.4, "بد": 0.3,
        "تعدیل منفی": 0.8, "تعدیل": 0.5,
    }

    # Intensifiers that amplify sentiment
    INTENSIFIERS: dict[str, float] = {
        "خیلی": 1.5, "بسیار": 1.5, "شدید": 2.0, "شدیداً": 2.0,
        "فوق‌العاده": 2.0, "بی‌نظیر": 2.0, "تاریخی": 1.5,
        "بی‌سابقه": 2.0, "کمنظیر": 1.5, "قابل توجه": 1.3,
        "بیش از حد": 1.5, "به شدت": 1.8, "به طور قابل توجهی": 1.5,
    }

    # Negation words
    NEGATION_WORDS: set[str] = {
        "عدم", "غیر", "نه", "نبود", "ندارد", "نمی", "نیست",
        "بدون", "به جز", "بجز", "به غیر از", "جدا از",
        "هنوز", "هنوز نه",
    }

    def analyze(self, text: str) -> dict[str, Any]:
        """Analyze sentiment of a single text.

        Returns dict with:
        - sentiment: str (positive/negative/neutral/mixed)
        - score: float (-1 to 1)
        - confidence: float (0-1)
        - details: dict with positive/negative counts
        """
        if not text:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0, "details": {}}

        text_lower = text.lower()

        # Tokenize once for word-boundary-aware counting.
        # Using re.findall with Unicode word chars avoids the substring
        # false-positive that str.count() causes (e.g. "سود" inside "سودآوری").
        tokens = set(re.findall(r"[\w\u0600-\u06FF]+", text_lower))
        # Also keep the raw text for position-based negation checks.

        # Count weighted positive/negative occurrences
        pos_score = 0.0
        neg_score = 0.0
        pos_count = 0
        neg_count = 0

        for word, weight in self.POSITIVE_WEIGHTS.items():
            # Count as substring but only if the word forms a standalone token
            # OR appears at a word boundary.  Fallback to .count() for short words.
            count = sum(1 for t in tokens if t == word) if len(word) >= 3 else text_lower.count(word)
            if count > 0:
                # Check negation
                negated_count = sum(
                    1 for _ in range(len(text_lower) - len(word) + 1)
                    if text_lower[_:_ + len(word)] == word
                    and any(
                        text_lower[max(0, _ - 15):_].strip().endswith(nw)
                        for nw in self.NEGATION_WORDS
                    )
                )
                effective_count = count - negated_count
                if effective_count > 0:
                    for _i in range(effective_count):
                        # Apply intensifier check
                        pos_prefix = text_lower[max(0, text_lower.find(word) - 30):text_lower.find(word)]
                        intensifier = 1.0
                        for int_word, int_factor in self.INTENSIFIERS.items():
                            if int_word in pos_prefix:
                                intensifier = int_factor
                                break
                        pos_score += weight * intensifier
                        pos_count += 1

                if negated_count > 0:
                    neg_score += weight * 0.5 * negated_count
                    neg_count += negated_count

        for word, weight in self.NEGATIVE_WEIGHTS.items():
            count = sum(1 for t in tokens if t == word) if len(word) >= 3 else text_lower.count(word)
            if count > 0:
                negated_count = sum(
                    1 for _ in range(len(text_lower) - len(word) + 1)
                    if text_lower[_:_ + len(word)] == word
                    and any(
                        text_lower[max(0, _ - 15):_].strip().endswith(nw)
                        for nw in self.NEGATION_WORDS
                    )
                )
                effective_count = count - negated_count
                if effective_count > 0:
                    for _i in range(effective_count):
                        neg_prefix = text_lower[max(0, text_lower.find(word) - 30):text_lower.find(word)]
                        intensifier = 1.0
                        for int_word, int_factor in self.INTENSIFIERS.items():
                            if int_word in neg_prefix:
                                intensifier = int_factor
                                break
                        neg_score += weight * intensifier
                        neg_count += 1

                if negated_count > 0:
                    pos_score += weight * 0.5 * negated_count
                    pos_count += negated_count

        # Calculate final score
        total = pos_score + neg_score
        if total == 0:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0, "details": {}}

        score = (pos_score - neg_score) / max(total, 0.001)
        score = max(-1.0, min(1.0, score))

        # Confidence based on match density
        total_terms = pos_count + neg_count
        text_length = len(text.split())
        confidence = min(1.0, total_terms / max(text_length * 0.1, 1))

        # Determine sentiment label
        if score > 0.3:
            sentiment = "positive"
        elif score < -0.3:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # Check for mixed sentiment
        if score > 0.2 and neg_count >= pos_count or score < -0.2 and pos_count >= neg_count:
            sentiment = "mixed"

        return {
            "sentiment": sentiment,
            "score": round(score, 4),
            "confidence": round(confidence, 4),
            "details": {
                "positive_score": round(pos_score, 4),
                "negative_score": round(neg_score, 4),
                "positive_terms": pos_count,
                "negative_terms": neg_count,
            },
        }

    def analyze_market_sentiment(
        self, texts: list[str]
    ) -> dict[str, Any]:
        """Analyze overall market sentiment from multiple texts."""
        if not texts:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0}

        results = [self.analyze(t) for t in texts]
        scores = [r["score"] for r in results if r["score"] != 0.0]

        if not scores:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0}

        avg_score = sum(scores) / len(scores)
        pos_count = sum(1 for s in scores if s > 0.3)
        neg_count = sum(1 for s in scores if s < -0.3)

        # Overall confidence
        confidence = sum(r["confidence"] for r in results) / len(results)

        if avg_score > 0.3:
            sentiment = "positive"
        elif avg_score < -0.3:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "sentiment": sentiment,
            "score": round(avg_score, 4),
            "confidence": round(confidence, 4),
            "distribution": {
                "positive": pos_count,
                "negative": neg_count,
                "neutral": len(scores) - pos_count - neg_count,
            },
            "details": results,
        }

    def analyze_symbol_sentiment(
        self, symbol: str, news_list: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze sentiment from news about a specific symbol."""
        texts = []
        for news in news_list:
            title = news.get("title", "")
            summary = news.get("summary", "")
            if title:
                texts.append(title)
            if summary:
                texts.append(summary)

        return self.analyze_market_sentiment(texts)

    @staticmethod
    def sentiment_to_emoji(sentiment: str) -> str:
        """Convert sentiment label to emoji."""
        return {
            "positive": "🟢",
            "negative": "🔴",
            "neutral": "⚪",
            "mixed": "🟡",
        }.get(sentiment, "⚪")
