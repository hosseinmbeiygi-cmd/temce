from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.time import now_iran

logger = get_logger(__name__)

SENTIMENT_LABELS = {
    "positive": ["رشد", "افزایش", "سود", "مثبت", "صعود", "بهبود", "افزایشی"],
    "negative": ["کاهش", "ضرر", "منفی", "سقوط", "ریزش", "کاهشی", "زیان"],
    "neutral": ["ثابت", "بدون تغییر", "خنثی"],
}

ENTITY_PATTERNS = {
    "instrument": ["نماد", "سهام", "شرکت"],
    "market": ["بورس", "فرابورس", "شاخص"],
    "economic": ["نرخ ارز", "طلا", "تورم", "نرخ بهره"],
    "regulatory": ["سازمان بورس", "ضوابط", "مقررات"],
}


class NewsEnricher:
    def enrich(self, data: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(data)
        title = enriched.get("title", "")
        body = enriched.get("body", "")
        full_text = f"{title} {body}"

        enriched["text_length"] = len(full_text)
        enriched["word_count"] = len(full_text.split()) if full_text else 0
        enriched["has_symbol_mention"] = any(word in full_text for word in ["#ف", "#ح", "#ک"])
        enriched["mentioned_symbols"] = self._extract_symbols(full_text)
        enriched["sentiment_label"] = self._detect_sentiment(full_text)
        enriched["entity_types"] = self._extract_entities(full_text)
        enriched["urgency"] = self._estimate_urgency(enriched)
        enriched["enriched_at"] = now_iran().isoformat()
        enriched.setdefault("extra", {})
        return enriched

    def _extract_symbols(self, text: str) -> list[str]:
        symbols = []
        for word in text.split():
            word_clean = word.strip("،؛.!?")
            if word_clean.startswith("#") and len(word_clean) > 1:
                symbols.append(word_clean)
        return symbols[:20]

    def _detect_sentiment(self, text: str) -> str:
        pos = sum(1 for w in SENTIMENT_LABELS["positive"] if w in text)
        neg = sum(1 for w in SENTIMENT_LABELS["negative"] if w in text)
        if pos > neg:
            return "positive"
        if neg > pos:
            return "negative"
        return "neutral"

    def _extract_entities(self, text: str) -> list[str]:
        found = []
        for etype, keywords in ENTITY_PATTERNS.items():
            for keyword in keywords:
                if keyword in text:
                    found.append(etype)
                    break
        return found

    def _estimate_urgency(self, data: dict[str, Any]) -> str:
        text = f"{data.get('title', '')} {data.get('body', '')}"
        urgent_keywords = ["فوری", "اضطراری", "لحظه‌ای", "شکست", "سقوط", "صف خرید", "صف فروش"]
        if any(k in text for k in urgent_keywords):
            return "high"
        important_keywords = ["افزایش سرمایه", "سود نقدی", "مجمع", "گزارش مالی"]
        if any(k in text for k in important_keywords):
            return "medium"
        return "low"

    def enrich_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.enrich(r) for r in records]
