from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.time import now_iran

logger = get_logger(__name__)

CATEGORY_KEYWORDS = {
    "financial_statements": ["صورت‌های مالی", "ترازنامه", "سود و زیان", "صورت جریان وجوه نقد"],
    "monthly_activity": ["فعالیت ماهانه", "عملکرد ماهانه"],
    "board_report": ["هیئت مدیره", "گزارش هیئت"],
    "capital_increase": ["افزایش سرمایه", "پیشنهاد افزایش"],
    "general_meeting": ["مجمع", "_general_meeting"],
    "dividend": ["سود نقدی", "تقسیم سود", " DPS"],
}


class CodalEnricher:
    def enrich(self, data: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(data)
        title = enriched.get("title", "")
        if isinstance(title, str):
            enriched["category"] = self._classify_disclosure(title)
            enriched["title_length"] = len(title)
            enriched["has_numbers"] = any(c.isdigit() for c in title)
            enriched["keyword_hits"] = self._extract_keywords(title)
        else:
            enriched["category"] = "unknown"
            enriched["title_length"] = 0
            enriched["has_numbers"] = False
            enriched["keyword_hits"] = []

        published_at = enriched.get("published_at")
        if published_at:
            enriched["is_recent"] = True
            enriched["publish_hour"] = self._extract_hour(published_at)
        else:
            enriched["is_recent"] = False
            enriched["publish_hour"] = None

        enriched["enriched_at"] = now_iran().isoformat()
        enriched.setdefault("extra", {})
        return enriched

    def _classify_disclosure(self, title: str) -> str:
        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in title:
                    return category
        return "other"

    def _extract_keywords(self, title: str) -> list[str]:
        found = []
        for _category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in title:
                    found.append(keyword)
        return found

    def _extract_hour(self, published_at: Any) -> int | None:
        try:
            if hasattr(published_at, "hour"):
                return published_at.hour
            if isinstance(published_at, str):
                return int(published_at.split("T")[1].split(":")[0])
        except (IndexError, ValueError):
            pass
        return None

    def enrich_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.enrich(r) for r in records]
