from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


try:
    import xml.etree.ElementTree as ET

    HAS_XML = True
except ImportError:
    HAS_XML = False


class RSSParser:
    def __init__(self) -> None:
        self.supported_formats = ["rss", "atom", "rdf"]

    def parse(self, raw_xml: str) -> list[dict[str, Any]]:
        if not HAS_XML:
            logger.warning("XML parsing not available")
            return []
        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as e:
            logger.error("Failed to parse RSS XML: %s", e)
            return []

        items: list[dict[str, Any]] = []
        namespace = self._detect_namespace(root.tag)

        for item in root.iter(f"{namespace}item") if namespace != "atom" else root.iter(f"{namespace}entry"):
            article = self._parse_item(item, namespace)
            if article:
                items.append(article)

        return items

    def _detect_namespace(self, tag: str) -> str:
        if "}" in tag:
            return tag[: tag.index("}") + 1]
        return ""

    def _parse_item(self, item: Any, ns: str) -> dict[str, Any]:
        def get_text(tag: str) -> str | None:
            elem = item.find(f"{ns}{tag}")
            if elem is not None and elem.text:
                return elem.text.strip()
            return None

        title = get_text("title")
        link = get_text("link")
        if ns == "atom":
            link_elem = item.find(f"{ns}link")
            if link_elem is not None:
                link = link_elem.get("href", link or "")
        description = get_text("description") or get_text("summary") or get_text("content")
        pub_date_str = get_text("pubDate") or get_text("published") or get_text("updated")
        pub_date: str | None = None
        if pub_date_str:
            try:
                dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
                pub_date = dt.isoformat()
            except ValueError:
                pub_date = pub_date_str

        return {
            "title": title or "",
            "link": link or "",
            "description": description or "",
            "published_at": pub_date or datetime.utcnow().isoformat(),
            "source": get_text("source") or get_text("generator") or "",
        }

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        return len(parsed) > 0
