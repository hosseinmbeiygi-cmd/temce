"""Gold and macro-economy news via public RSS feeds.

Covers both international and Iranian domestic news sources without
requiring any API key.  All feeds are public and free.

International:
  - Kitco Gold News  (https://www.kitco.com/rss/kitconews.xml)
  - FXStreet Gold    (https://www.fxstreet.com/rss/news?category=metals)

Iranian domestic:
  - SANA (بورس کالا) (https://sana.ir/fa/rss/goldcoin)
  - IBNA (بانک مرکزی) (https://www.ibna.ir/rss)
  - tgju.org news    (https://www.tgju.org/rss/news)

Extra (my additions — high value for gold trading signals):
  - Reuters Commodities (https://feeds.reuters.com/reuters/commoditiesNews)
  - Bloomberg Markets   (https://feeds.bloomberg.com/markets/news.rss)
  - Mining.com          (https://www.mining.com/feed/)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider

logger = get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS: float = 10.0

# ── Feed catalogue ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RSSFeedConfig:
    name: str
    url: str
    language: str   # "en" | "fa"
    category: str   # "international" | "domestic"
    source: str     # human-readable source name


GOLD_RSS_FEEDS: dict[str, RSSFeedConfig] = {
    "kitco": RSSFeedConfig(
        name="kitco",
        url="https://www.kitco.com/rss/kitconews.xml",
        language="en",
        category="international",
        source="Kitco News",
    ),
    "fxstreet_gold": RSSFeedConfig(
        name="fxstreet_gold",
        url="https://www.fxstreet.com/rss/news?category=metals",
        language="en",
        category="international",
        source="FXStreet",
    ),
    "reuters_commodities": RSSFeedConfig(
        name="reuters_commodities",
        url="https://feeds.reuters.com/reuters/commoditiesNews",
        language="en",
        category="international",
        source="Reuters",
    ),
    "mining_com": RSSFeedConfig(
        name="mining_com",
        url="https://www.mining.com/feed/",
        language="en",
        category="international",
        source="Mining.com",
    ),
    "sana": RSSFeedConfig(
        name="sana",
        url="https://sana.ir/fa/rss/goldcoin",
        language="fa",
        category="domestic",
        source="سنا - بورس کالا",
    ),
    "ibna": RSSFeedConfig(
        name="ibna",
        url="https://www.ibna.ir/rss",
        language="fa",
        category="domestic",
        source="ایبنا - بانک مرکزی",
    ),
    "tgju_news": RSSFeedConfig(
        name="tgju_news",
        url="https://www.tgju.org/rss/news",
        language="fa",
        category="domestic",
        source="تgju.org",
    ),
}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NewsItem:
    """One news article from an RSS feed."""

    title: str
    url: str
    published_at: str    # ISO-8601 string (best-effort from pubDate)
    summary: str
    source: str
    feed_name: str
    language: str
    category: str        # "international" | "domestic"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ── Low-level parser ──────────────────────────────────────────────────────────

def _parse_rss_xml(xml_text: str, feed: RSSFeedConfig) -> list[NewsItem]:
    """Parse standard RSS 2.0 XML into NewsItem list."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("Feed %s could not be parsed: malformed XML: %s", feed.url, exc)
        return []

    # Support both <rss><channel><item> and Atom <feed><entry>
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[NewsItem] = []

    # RSS 2.0
    for item in root.findall(".//item"):
        title   = (item.findtext("title")   or "").strip()
        link    = (item.findtext("link")    or "").strip()
        pub     = (item.findtext("pubDate") or "").strip()
        # description may contain child HTML elements — itertext collects all text
        desc_el = item.find("description")
        desc    = " ".join(desc_el.itertext()).strip() if desc_el is not None else ""

        published_at = _parse_date(pub)
        items.append(NewsItem(
            title      = title,
            url        = link,
            published_at = published_at,
            summary    = _strip_html(desc)[:400],
            source     = feed.source,
            feed_name  = feed.name,
            language   = feed.language,
            category   = feed.category,
        ))

    # Atom
    if not items:
        for entry in root.findall("atom:entry", ns):
            title  = (entry.findtext("atom:title",   namespaces=ns) or "").strip()
            link_el = entry.find("atom:link",         namespaces=ns)
            link   = link_el.get("href", "") if link_el is not None else ""
            summ   = (entry.findtext("atom:summary", namespaces=ns) or "").strip()
            pub    = (entry.findtext("atom:published",namespaces=ns) or "").strip()
            items.append(NewsItem(
                title      = title,
                url        = link,
                published_at = pub or datetime.now(UTC).isoformat(),
                summary    = _strip_html(summ)[:400],
                source     = feed.source,
                feed_name  = feed.name,
                language   = feed.language,
                category   = feed.category,
            ))

    return items


def _parse_date(pub_date: str) -> str:
    """Convert RFC-2822 pubDate to ISO-8601 string; fall back to now."""
    if not pub_date:
        return datetime.now(UTC).isoformat()
    try:
        dt = parsedate_to_datetime(pub_date)
        return dt.isoformat()
    except Exception:
        return pub_date  # keep original if unparseable


def _strip_html(text: str) -> str:
    """Remove simple HTML tags from RSS description snippets."""
    import re
    return re.sub(r"<[^>]+>", " ", text).strip()


# ── HTTP client ───────────────────────────────────────────────────────────────

class RSSNewsClient:
    """Fetch one or more RSS feeds and return parsed NewsItem lists.

    Inject ``client`` in tests to avoid real network calls.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def fetch_feed(self, feed: RSSFeedConfig) -> list[NewsItem]:
        """Fetch and parse a single RSS feed."""
        close_client = self._client is None
        http = self._client or httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Temce GoldDesk RSS reader)"},
        )
        try:
            resp = await http.get(feed.url)
            resp.raise_for_status()
            xml_text = resp.text
        except Exception as exc:
            logger.warning("RSS fetch %s: %s", feed.name, exc)
            return []
        finally:
            if close_client:
                await http.aclose()

        items = _parse_rss_xml(xml_text, feed)
        logger.debug("Parsed %d items from RSS feed", len(items))
        return items

    async def fetch_feeds(
        self,
        feed_names: list[str] | None = None,
        *,
        category: str | None = None,
        language: str | None = None,
    ) -> list[NewsItem]:
        """Fetch multiple feeds concurrently and merge results.

        Args:
            feed_names: list of feed keys from GOLD_RSS_FEEDS (all if None).
            category: filter by ``"international"`` or ``"domestic"``.
            language: filter by ``"en"`` or ``"fa"``.
        """
        import asyncio

        feeds = list(GOLD_RSS_FEEDS.values())
        if feed_names is not None:
            feeds = [f for f in feeds if f.name in feed_names]
        if category:
            feeds = [f for f in feeds if f.category == category]
        if language:
            feeds = [f for f in feeds if f.language == language]

        results = await asyncio.gather(
            *[self.fetch_feed(f) for f in feeds],
            return_exceptions=True,
        )

        all_items: list[NewsItem] = []
        ok_count = 0
        empty_count = 0
        fail_count = 0
        for feed, result in zip(feeds, results):
            if isinstance(result, Exception):
                logger.warning("RSS fetch %s: unexpected exception: %s", feed.name, result)
                fail_count += 1
            elif isinstance(result, list):
                all_items.extend(result)
                if result:
                    ok_count += 1
                else:
                    empty_count += 1

        logger.info(
            "RSS fetch %s: %d/%d feeds returned articles, %d empty, %d failed — %s",
            "rss_mixed" if not feed_names else "_".join(feed_names),
            ok_count,
            len(feeds),
            empty_count,
            fail_count,
            ", ".join(
                f"{f.name} (parse_error: {r})"
                if isinstance(r, Exception) else
                f"{f.name} (empty)" if isinstance(r, list) and not r else f"{f.name}"
                for f, r in zip(feeds, results)
            ),
        )
        return all_items


# ── BaseProvider wrapper ──────────────────────────────────────────────────────

class GoldNewsRSSProvider(BaseProvider):
    """Multi-feed RSS news provider for gold market news.

    Args:
        client: injectable httpx.AsyncClient for testing.
        feed_names: subset of feed keys to fetch (all if None).
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        feed_names: list[str] | None = None,
    ) -> None:
        super().__init__(name="gold_news_rss")
        self._rss = RSSNewsClient(client=client)
        self._feed_names = feed_names

    async def fetch(
        self,
        category: str | None = None,
        language: str | None = None,
        feed_names: list[str] | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> Result[Any]:
        """Return recent gold news articles from RSS feeds.

        Args:
            category: ``"international"`` | ``"domestic"`` | None (all).
            language: ``"en"`` | ``"fa"`` | None (all).
            feed_names: specific feeds to include (defaults to instance setting).
            limit: max articles to return.
        """
        feeds = feed_names or self._feed_names
        items = await self._rss.fetch_feeds(
            feed_names=feeds,
            category=category,
            language=language,
        )
        if not items:
            return Result.fail("No news articles returned from RSS feeds")

        # Sort newest-first (best effort based on published_at ISO string)
        items_sorted = sorted(items, key=lambda i: i.published_at, reverse=True)
        trimmed = items_sorted[:limit]

        data = [
            {
                "title":        i.title,
                "url":          i.url,
                "published_at": i.published_at,
                "summary":      i.summary,
                "source":       i.source,
                "feed_name":    i.feed_name,
                "language":     i.language,
                "category":     i.category,
            }
            for i in trimmed
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        items = await self._rss.fetch_feeds(
            feed_names=["kitco"],  # lightest check
        )
        if items:
            return {"healthy": True, "message": f"kitco: {len(items)} articles"}
        return {"healthy": False, "message": "Kitco RSS feed unavailable"}
