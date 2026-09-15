"""NewsFetcher — Fetch news from multiple Persian financial sources (Level 16).

Supports:
- RSS feeds from major Persian financial news sites
- BrsApi news endpoints
- Codal announcements

Note: Uses httpx for async HTTP, falls back to requests for sync.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# Try to import feedparser once
try:
    import feedparser as _feedparser

    HAS_FEEDPARSER = True
except ImportError:
    _feedparser = None
    HAS_FEEDPARSER = False
    logger.warning("feedparser not installed — RSS news fetching disabled")

# Try to import httpx for async HTTP
try:
    import httpx as _httpx

    HAS_HTTPX = True
except ImportError:
    _httpx = None
    HAS_HTTPX = False


class NewsFetcher:
    """Fetch financial news from multiple Persian sources."""

    RSS_SOURCES: dict[str, str] = {
        "بورس پرس": "https://boursepress.ir/feed",
        "اقتصاد نیوز": "https://www.eghtesadnews.com/feed",
        "فردای اقتصاد": "https://www.fardayeeghtesad.com/rss",
        "ایسنا (اقتصادی)": "https://www.isna.ir/rss/tp/68",
        "اقتصاد آنلاین": "https://www.eghtesadonline.com/feeds",
        "اکوایران": "https://ecoiran.com/feeds",
        "تجارت نیوز": "https://tejaratnews.com/feed",
    }

    API_ENDPOINTS: dict[str, str] = {
        "brsapi": "https://Api.BrsApi.ir/Market/News.php",
        "tsetmc": "https://api.tsetmc.com/api/News/GetBySymbol",
    }

    def __init__(self, brsapi_key: str | None = None):
        self._brsapi_key = brsapi_key
        self._timeout = 10.0
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    async def fetch_news_for_symbol(self, symbol: str, days_back: int = 3) -> list[dict[str, Any]]:
        """Fetch news related to a specific symbol (async)."""
        import time

        cache_key = f"news:{symbol}:{days_back}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[1] < self._cache_ttl:
            return cached[0]

        # Run blocking I/O in thread pool to avoid blocking event loop
        all_news = await asyncio.to_thread(self._fetch_all, symbol, days_back)

        result = all_news[:20]
        self._cache[cache_key] = (result, time.time())
        return result

    async def fetch_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """Fetch general market news (async)."""
        import time

        cache_key = f"market_news:{days_back}"
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached[1] < self._cache_ttl:
            return cached[0]

        all_news = await asyncio.to_thread(self._fetch_market_news_sync, days_back)

        result = all_news[:30]
        self._cache[cache_key] = (result, time.time())
        return result

    def _fetch_all(self, symbol: str, days_back: int) -> list[dict[str, Any]]:
        """Synchronous fetching wrapper."""
        all_news = []
        all_news.extend(self._fetch_from_rss(symbol, days_back))
        all_news.extend(self._fetch_from_brsapi(symbol, days_back))
        return self._deduplicate(all_news)

    def _fetch_from_rss(self, symbol: str, days_back: int) -> list[dict[str, Any]]:
        """Fetch news from RSS feeds."""
        if not HAS_FEEDPARSER:
            return []

        news_list = []
        cutoff = datetime.now() - timedelta(days=days_back)

        for source_name, rss_url in self.RSS_SOURCES.items():
            try:
                feed = _feedparser.parse(rss_url)
                for entry in feed.entries[:15]:
                    if not self._is_related_to_symbol(
                        entry.get("title", ""), symbol
                    ) and not self._is_related_to_symbol(entry.get("summary", ""), symbol):
                        continue

                    pub_date = entry.get("published", "")
                    pub_dt = self._parse_date(pub_date) if pub_date else None
                    if pub_dt and pub_dt < cutoff:
                        continue

                    news_list.append(
                        {
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", "")[:300],
                            "link": entry.get("link", ""),
                            "source": source_name,
                            "published": pub_date,
                            "symbol": symbol,
                        }
                    )
            except Exception as e:
                logger.debug(f"RSS fetch error {source_name}: {e}")

        return news_list

    def _fetch_market_news_sync(self, days_back: int) -> list[dict[str, Any]]:
        """Synchronous market news fetch."""
        if not HAS_FEEDPARSER:
            return []

        all_news = []
        cutoff = datetime.now() - timedelta(days=days_back)

        for source_name, rss_url in self.RSS_SOURCES.items():
            try:
                feed = _feedparser.parse(rss_url)
                for entry in feed.entries[:10]:
                    pub_date = entry.get("published", "")
                    pub_dt = self._parse_date(pub_date) if pub_date else None
                    if pub_dt and pub_dt < cutoff:
                        continue

                    all_news.append(
                        {
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", "")[:300],
                            "link": entry.get("link", ""),
                            "source": source_name,
                            "published": pub_date,
                            "symbol": None,
                        }
                    )
            except Exception as e:
                logger.debug(f"RSS fetch error {source_name}: {e}")

        return self._deduplicate(all_news)

    def _fetch_from_brsapi(self, symbol: str, days_back: int) -> list[dict[str, Any]]:
        """Fetch news from BrsApi."""
        news_list = []
        if not self._brsapi_key:
            return news_list

        try:
            if HAS_HTTPX:
                import httpx

                with httpx.Client() as client:
                    url = self.API_ENDPOINTS["brsapi"]
                    params = {"key": self._brsapi_key, "l18": symbol, "days": days_back}
                    resp = client.get(url, params=params, timeout=self._timeout)
            else:
                import requests

                url = self.API_ENDPOINTS["brsapi"]
                resp = requests.get(
                    url, params={"key": self._brsapi_key, "l18": symbol, "days": days_back}, timeout=self._timeout
                )

            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    for item in data:
                        news_list.append(
                            {
                                "title": item.get("title", ""),
                                "summary": item.get("body", item.get("summary", ""))[:300],
                                "link": item.get("link", ""),
                                "source": "BrsApi",
                                "published": item.get("date", item.get("published", "")),
                                "symbol": symbol,
                            }
                        )
        except Exception as e:
            logger.debug(f"BrsApi news error: {e}")

        return news_list

    @staticmethod
    def _is_related_to_symbol(text: str, symbol: str) -> bool:
        if not text or not symbol:
            return False
        return symbol.lower() in text.lower()

    @staticmethod
    def _parse_date(date_string: str) -> datetime | None:
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d %H:%M:%S",
            "%d %b %Y %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def _deduplicate(news_list: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for item in news_list:
            title = item.get("title", "").strip()
            if title and title not in seen:
                seen.add(title)
                unique.append(item)
        return unique
