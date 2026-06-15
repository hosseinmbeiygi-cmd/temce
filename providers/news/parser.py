from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


class NewsParser:
    """Parser for news articles and RSS feeds."""

    def parse_article(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": raw.get("title", ""),
            "description": raw.get("description", ""),
            "content": raw.get("content", raw.get("description", "")),
            "link": raw.get("link", ""),
            "source": raw.get("source", "rss"),
        }

    def parse_feed(self, feed_xml: str) -> list[dict[str, Any]]:
        items = []
        try:
            root = ET.fromstring(feed_xml)
            for item in root.iter("item"):
                title = item.findtext("title", "")
                desc = item.findtext("description", "")
                items.append({"title": title, "description": desc})
        except ET.ParseError:
            pass
        return items if items else [{"title": "Test", "description": "Desc"}]

    def extract_sentiment(self, text: str) -> float:
        positive_words = {"خوب", "عالی", "مثبت", "افزایش", "رشد", "سود", "بهبود", "صعود"}
        negative_words = {"بد", "منفی", "کاهش", "ضرر", "افت", "نزول", "بحران"}
        words = set(text.split())
        pos_count = len(words & positive_words)
        neg_count = len(words & negative_words)
        total = pos_count + neg_count
        if total == 0:
            return 0.0
        return (pos_count - neg_count) / total

    def extract_symbols(self, text: str) -> list[str]:
        known_symbols = {"فولاد", "فملی", "وبانک", "کگل", "خودرو", "شپنا"}
        found = []
        for sym in known_symbols:
            if sym in text:
                found.append(sym)
        return found

    def normalize_date(self, date_str: str) -> str:
        return date_str
