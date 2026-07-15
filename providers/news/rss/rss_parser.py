from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


try:
    import xml.etree.ElementTree as ET

    HAS_XML = True
except ImportError:
    HAS_XML = False


# Common RSS date formats for parsing
_RSS_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",   # RFC 2822 (standard RSS)
    "%a, %d %b %Y %H:%M:%S %Z",   # RFC 2822 with timezone name
    "%Y-%m-%dT%H:%M:%S%z",          # ISO 8601
    "%Y-%m-%dT%H:%M:%S.%f%z",       # ISO 8601 with microseconds
    "%Y-%m-%dT%H:%M:%S",            # ISO 8601 (naive)
    "%Y-%m-%d %H:%M:%S",            # Common database format
]


class RSSParser:
    """Robust parser for RSS 2.0, Atom, and RDF feed formats."""

    def __init__(self) -> None:
        self.supported_formats = ["rss", "atom", "rdf"]

    def parse(self, raw_xml: str) -> list[dict[str, Any]]:
        """Parse an RSS/Atom/RDF feed and return a list of article dicts."""
        if not HAS_XML:
            logger.warning("XML parsing not available — install xml.etree.ElementTree")
            return []

        if not raw_xml or not raw_xml.strip():
            logger.warning("Empty XML content passed to RSSParser.parse")
            return []

        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as e:
            logger.error("Failed to parse RSS XML: %s", e)
            return []

        items: list[dict[str, Any]] = []
        namespace = self._detect_namespace(root.tag)

        element_tag = f"{namespace}entry" if namespace and "atom" in namespace.lower() else f"{namespace}item"
        for item in root.iter(element_tag):
            article = self._parse_item(item, namespace)
            if article:
                items.append(article)

        logger.debug("Parsed %d items from RSS feed", len(items))
        return items

    def _detect_namespace(self, tag: str) -> str:
        """Extract XML namespace prefix from a tag."""
        if "}" in tag:
            return tag[: tag.index("}") + 1]
        return ""

    def _parse_item(self, item: Any, ns: str) -> dict[str, Any]:
        """Parse a single RSS item / Atom entry element."""
        def get_text(tag: str) -> str | None:
            elem = item.find(f"{ns}{tag}")
            if elem is not None and elem.text:
                return elem.text.strip()
            return None

        title = get_text("title")
        link = get_text("link")
        if "atom" in ns.lower():
            link_elem = item.find(f"{ns}link")
            if link_elem is not None:
                link = link_elem.get("href", link or "")
        description = get_text("description") or get_text("summary") or get_text("content")
        pub_date_str = get_text("pubDate") or get_text("published") or get_text("updated")
        pub_date: str | None = None
        if pub_date_str:
            pub_date = self._parse_date(pub_date_str) or pub_date_str

        # Extract category (may appear multiple times; take first)
        category = get_text("category") or ""

        return {
            "title": title or "",
            "link": link or "",
            "description": description or "",
            "published_at": pub_date or datetime.now(UTC).isoformat(),
            "source": get_text("source") or get_text("generator") or "",
            "category": category,
        }

    def _parse_date(self, date_str: str) -> str | None:
        """Parse a date string using common RSS formats, returning ISO 8601 or None."""
        for fmt in _RSS_DATE_FORMATS:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Convert to UTC-aware ISO format
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt.isoformat()
            except (ValueError, OverflowError):
                continue
        return None

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        """Validate that parsed results are non-empty."""
        return len(parsed) > 0
