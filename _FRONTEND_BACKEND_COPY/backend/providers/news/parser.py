from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class NewsParser:
    """Parser for news articles and RSS feeds."""

    def parse_article(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Parse a raw article dict into a standardized format."""
        return {
            "title": raw.get("title", ""),
            "description": raw.get("description", ""),
            "content": raw.get("content", raw.get("description", "")),
            "link": raw.get("link", ""),
            "source": raw.get("source", "rss"),
        }

    def parse_feed(self, feed_xml: str) -> list[dict[str, Any]]:
        """Parse an RSS/Atom XML feed string into a list of article dicts.
        Returns an empty list on parse failure — never returns fake/test data.
        """
        items: list[dict[str, Any]] = []
        if not feed_xml or not feed_xml.strip():
            return items
        try:
            root = ET.fromstring(feed_xml)
            # Detect and strip namespace prefix
            ns = ""
            if "}" in root.tag:
                ns = root.tag[: root.tag.index("}") + 1]
            # Handle both RSS <item> and Atom <entry>
            element_tag = f"{ns}item"
            is_atom = ns and "atom" in root.tag.lower()
            if is_atom:
                element_tag = f"{ns}entry"
            for item in root.iter(element_tag):
                title = item.findtext(f"{ns}title", "")
                desc = (
                    item.findtext(f"{ns}description", "")
                    or item.findtext(f"{ns}summary", "")
                    or item.findtext(f"{ns}content", "")
                )
                link_elem = item.find(f"{ns}link")
                link = link_elem.get("href") or link_elem.text or "" if link_elem is not None else ""
                pub_date_elem = item.find(f"{ns}pubDate") or item.find(f"{ns}published") or item.find(f"{ns}updated")
                pub_date = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ""
                items.append(
                    {
                        "title": title or "",
                        "description": desc or "",
                        "link": link,
                        "published_at": self.normalize_date(pub_date),
                    }
                )
        except ET.ParseError:
            logger.warning("Failed to parse RSS/XML feed", exc_info=True)
        return items

    def extract_sentiment(self, text: str) -> float:
        """Extract a simple sentiment score (-1.0 to 1.0) from text."""
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
        """Extract known Iranian stock symbols from text."""
        known_symbols = {"فولاد", "فملی", "وبانک", "کگل", "خودرو", "شپنا"}
        found: list[str] = []
        for sym in known_symbols:
            if sym in text:
                found.append(sym)
        return found

    def normalize_date(self, date_str: str) -> str:
        """Normalize a date string to ISO 8601 UTC format.

        Handles common RSS/Atom date formats and returns ISO 8601 string.
        Falls back to the original string if parsing fails.
        """
        from datetime import datetime

        if not date_str or not date_str.strip():
            return datetime.now(UTC).isoformat()

        _formats = [
            "%a, %d %b %Y %H:%M:%S %z",  # RFC 2822 (standard RSS)
            "%a, %d %b %Y %H:%M:%S %Z",  # RFC 2822 with timezone name
            "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601
            "%Y-%m-%dT%H:%M:%S.%f%z",  # ISO 8601 with microseconds
            "%Y-%m-%dT%H:%M:%S",  # ISO 8601 (naive)
            "%Y-%m-%d %H:%M:%S",  # Common database format
            "%Y/%m/%d",  # Shamsi-like pattern (converted as-is)
            "%Y-%m-%d",  # Simple date
        ]
        for fmt in _formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt.isoformat()
            except (ValueError, OverflowError):
                continue
        # If all fail, return original string
        logger.debug("Could not normalize date: %s", date_str)
        return date_str
