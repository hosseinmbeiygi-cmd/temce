"""Gold and macro-economy news via public RSS feeds.

International sources (with automatic fallback to Google News RSS when primary
URLs return 403/404 or time-out):
  - Kitco Gold News  — primary + Google News fallback
  - FXStreet Gold    — primary + Google News fallback
  - Reuters Markets  — updated URL + Google News fallback
  - Mining.com       — primary + Google News fallback

Iranian domestic:
  - SANA (بورس کالا) — https://sana.ir/fa/rss/goldcoin
  - IBNA (بانک مرکزی) — https://www.ibna.ir/rss
  - tgju.org news    — https://www.tgju.org/rss/news

Each feed has a list of ``url_candidates`` tried in order; the first that
returns a parseable XML response wins.  Google News RSS is always reachable
and is listed last as the guaranteed fallback for blocked sources.
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

DEFAULT_TIMEOUT_SECONDS: float = 12.0

# Chrome 131 on Windows — widely accepted by news sites
_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_BROWSER_HEADERS = {
    "User-Agent": _CHROME_UA,
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


# ── Feed catalogue ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RSSFeedConfig:
    name: str
    url: str                          # primary URL (also url_candidates[0])
    url_candidates: tuple[str, ...]   # tried in order; first working wins
    language: str                     # "en" | "fa"
    category: str                     # "international" | "domestic"
    source: str


def _gnews(query: str) -> str:
    """Build a Google News RSS URL for ``query``."""
    import urllib.parse
    q = urllib.parse.quote_plus(query)
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


GOLD_RSS_FEEDS: dict[str, RSSFeedConfig] = {
    "kitco": RSSFeedConfig(
        name="kitco",
        url="https://www.kitco.com/rss/kitconews.xml",
        url_candidates=(
            "https://www.kitco.com/rss/kitconews.xml",
            "https://news.kitco.com/feeds/gold.xml",
            "https://www.kitco.com/rss/gold.xml",
            _gnews("gold price site:kitco.com"),
        ),
        language="en",
        category="international",
        source="Kitco News",
    ),
    "fxstreet_gold": RSSFeedConfig(
        name="fxstreet_gold",
        url="https://www.fxstreet.com/rss/news?category=metals",
        url_candidates=(
            "https://www.fxstreet.com/rss/news?category=metals",
            "https://www.fxstreet.com/rss/news",
            _gnews("gold silver XAU site:fxstreet.com"),
        ),
        language="en",
        category="international",
        source="FXStreet",
    ),
    "reuters_commodities": RSSFeedConfig(
        name="reuters_commodities",
        url="https://feeds.reuters.com/reuters/commoditiesNews",
        url_candidates=(
            "https://feeds.reuters.com/reuters/commoditiesNews",
            "https://www.reuters.com/rssFeed/commoditiesNews",
            "https://www.reuters.com/rssFeed/marketsNews",
            _gnews("gold price commodities site:reuters.com"),
        ),
        language="en",
        category="international",
        source="Reuters",
    ),
    "mining_com": RSSFeedConfig(
        name="mining_com",
        url="https://www.mining.com/feed/",
        url_candidates=(
            "https://www.mining.com/feed/",
            "https://www.mining.com/top-stories/gold/feed/",
            "https://www.mining.com/category/gold/feed/",
            _gnews("gold mine production site:mining.com"),
        ),
        language="en",
        category="international",
        source="Mining.com",
    ),
    "sana": RSSFeedConfig(
        name="sana",
        url="https://sana.ir/fa/rss/goldcoin",
        url_candidates=(
            "https://sana.ir/fa/rss/goldcoin",
            "https://www.sana.ir/fa/rss/goldcoin",
        ),
        language="fa",
        category="domestic",
        source="سنا - بورس کالا",
    ),
    "ibna": RSSFeedConfig(
        name="ibna",
        url="https://www.ibna.ir/rss",
        url_candidates=(
            "https://www.ibna.ir/rss",
            "https://www.ibna.ir/rss/economy",
        ),
        language="fa",
        category="domestic",
        source="ایبنا - بانک مرکزی",
    ),
    "tgju_news": RSSFeedConfig(
        name="tgju_news",
        url="https://www.tgju.org/rss/news",
        url_candidates=(
            "https://www.tgju.org/rss/news",
            "https://tgju.org/rss/news",
        ),
        language="fa",
        category="domestic",
        source="tgju.org",
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

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[NewsItem] = []

    # RSS 2.0
    for item in root.findall(".//item"):
        title   = (item.findtext("title")   or "").strip()
        link    = (item.findtext("link")    or "").strip()
        pub     = (item.findtext("pubDate") or "").strip()
        desc_el = item.find("description")
        desc    = " ".join(desc_el.itertext()).strip() if desc_el is not None else ""

        # Google News RSS: source element has the original outlet name
        src_el = item.find("source")
        source = src_el.text.strip() if src_el is not None and src_el.text else feed.source

        # Strip " - Outlet Name" suffix that Google News appends to titles
        display_title = title
        if src_el is not None and src_el.text and title.endswith(f" - {src_el.text.strip()}"):
            display_title = title[: -(len(src_el.text.strip()) + 3)].strip()

        items.append(NewsItem(
            title        = display_title,
            url          = link,
            published_at = _parse_date(pub),
            summary      = _strip_html(desc)[:400],
            source       = source,
            feed_name    = feed.name,
            language     = feed.language,
            category     = feed.category,
        ))

    # Atom
    if not items:
        for entry in root.findall("atom:entry", ns):
            title  = (entry.findtext("atom:title",    namespaces=ns) or "").strip()
            link_el = entry.find("atom:link",          namespaces=ns)
            link   = link_el.get("href", "") if link_el is not None else ""
            summ   = (entry.findtext("atom:summary",  namespaces=ns) or "").strip()
            pub    = (entry.findtext("atom:published", namespaces=ns) or "").strip()
            items.append(NewsItem(
                title        = title,
                url          = link,
                published_at = pub or datetime.now(UTC).isoformat(),
                summary      = _strip_html(summ)[:400],
                source       = feed.source,
                feed_name    = feed.name,
                language     = feed.language,
                category     = feed.category,
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
        return pub_date


def _strip_html(text: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", text).strip()


# ── HTTP client ───────────────────────────────────────────────────────────────

class RSSNewsClient:
    """Fetch one or more RSS feeds and return parsed NewsItem lists.

    Each feed is tried with multiple URL candidates in order; the first that
    returns valid XML wins.  Inject ``client`` in tests.
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
        """Fetch and parse a single RSS feed, trying all URL candidates."""
        close_client = self._client is None
        http = self._client or httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            headers=_BROWSER_HEADERS,
        )
        try:
            return await self._try_candidates(http, feed)
        finally:
            if close_client:
                await http.aclose()

    async def _try_candidates(
        self, http: httpx.AsyncClient, feed: RSSFeedConfig
    ) -> list[NewsItem]:
        candidates = feed.url_candidates or (feed.url,)
        last_exc: str = ""
        for url in candidates:
            try:
                resp = await http.get(url)
                if resp.status_code in (403, 404, 410, 451):
                    logger.debug("RSS %s: %d at %s, trying next", feed.name, resp.status_code, url)
                    last_exc = f"HTTP {resp.status_code}"
                    continue
                resp.raise_for_status()
                items = _parse_rss_xml(resp.text, feed)
                if items:
                    if url != feed.url:
                        logger.info("RSS %s: primary blocked, using fallback %s", feed.name, url)
                    return items
                # 200 OK but empty XML — try next candidate
                last_exc = "empty feed"
            except httpx.TimeoutException:
                last_exc = "timeout"
                logger.debug("RSS %s: timeout at %s, trying next", feed.name, url)
            except Exception as exc:
                last_exc = str(exc)
                logger.debug("RSS %s: error at %s: %s", feed.name, url, exc)

        logger.warning("RSS fetch %s: all %d candidates failed (%s)", feed.name, len(candidates), last_exc)
        return []

    async def fetch_feeds(
        self,
        feed_names: list[str] | None = None,
        *,
        category: str | None = None,
        language: str | None = None,
    ) -> list[NewsItem]:
        """Fetch multiple feeds concurrently and merge results."""
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
            "RSS multi-fetch: %d/%d feeds OK, %d empty, %d failed",
            ok_count, len(feeds), empty_count, fail_count,
        )
        return all_items


# ── BaseProvider wrapper ──────────────────────────────────────────────────────

class GoldNewsRSSProvider(BaseProvider):
    """Multi-feed RSS news provider for gold market news."""

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
        feeds = feed_names or self._feed_names
        items = await self._rss.fetch_feeds(
            feed_names=feeds,
            category=category,
            language=language,
        )
        if not items:
            return Result.fail("No news articles returned from RSS feeds")

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
        items = await self._rss.fetch_feeds(feed_names=["ibna"])
        if items:
            return {"healthy": True, "message": f"ibna: {len(items)} articles"}
        return {"healthy": False, "message": "RSS feeds unavailable"}
