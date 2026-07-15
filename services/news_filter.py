from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class NewsFilter:
    """Filters news articles by multiple criteria.

    Filters applied in order (early filters are cheaper):
    1. Min content length — discard empty/short articles
    2. Date range — keep only articles within [from_date, to_date]
    3. Source whitelist/blacklist — include/exclude specific sources
    4. Category filter — keep only articles matching category(ies)
    5. Keyword filter — keep articles containing specific keywords
    6. Symbol filter — keep articles mentioning specific stock symbols
    """

    def __init__(
        self,
        min_content_length: int = 30,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        sources_whitelist: list[str] | None = None,
        sources_blacklist: list[str] | None = None,
        categories: list[str] | None = None,
        keywords: list[str] | None = None,
        symbols: list[str] | None = None,
    ) -> None:
        self.min_content_length = min_content_length
        self.from_date = from_date
        self.to_date = to_date
        self.sources_whitelist = set(s.lower() for s in sources_whitelist) if sources_whitelist else None
        self.sources_blacklist = set(s.lower() for s in sources_blacklist) if sources_blacklist else None
        self.categories = set(c.lower() for c in categories) if categories else None
        self.keywords = [k.lower() for k in keywords] if keywords else None
        self.symbols = set(s.strip() for s in symbols) if symbols else None

        # Persian economy-related keywords for stock market relevance
        self._default_economy_keywords: list[str] = [
            "بورس", "سهام", "سهم", "شاخص", "معامله", "معاملات",
            "قیمت", "ارزش", "سود", "زیان", "تولید", "صادرات",
            "واردات", "تورم", "نرخ", "دلار", "ارز", "طلا",
            "نفت", "پتروشیمی", "فولاد", "خودرو", "بانک",
            "سرمایه", "سرمایه‌گذاری", "تسهیلات", "بهره",
            "اقتصاد", "مالی", "بودجه", "تحریم", "برجام",
            "صنعت", "بازار", "رشد", "کاهش", "افزایش",
        ]

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse a date string from RSS feeds (RFC 2822, ISO 8601, etc.)."""
        if not date_str:
            return None

        formats = [
            "%a, %d %b %Y %H:%M:%S %z",   # RFC 2822
            "%a, %d %b %Y %H:%M:%S %Z",   # RFC 2822 with timezone name
            "%Y-%m-%dT%H:%M:%S%z",         # ISO 8601
            "%Y-%m-%dT%H:%M:%S.%f%z",      # ISO 8601 with microseconds
            "%Y-%m-%dT%H:%M:%S",           # ISO 8601 naive
            "%Y-%m-%d %H:%M:%S",           # Common DB format
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except (ValueError, OverflowError):
                continue
        return None

    def _get_article_source(self, article: dict[str, Any]) -> str:
        """Extract source name from article dict."""
        return (article.get("source") or "").lower()

    def _get_article_text(self, article: dict[str, Any]) -> str:
        """Get combined text content from article for keyword matching."""
        title = (article.get("title") or "").lower()
        desc = (article.get("description") or article.get("content") or "").lower()
        return f"{title} {desc}"

    def passes(self, article: dict[str, Any]) -> tuple[bool, str]:
        """Check if an article passes all active filters.

        Returns (True, "") if passed, or (False, reason) if filtered out.
        """
        title = article.get("title") or ""
        desc = article.get("description") or ""
        content = article.get("content") or desc

        # Filter 1: Min content length
        total_text = f"{title} {desc} {content}"
        if len(total_text.strip()) < self.min_content_length:
            return False, f"content_too_short ({len(total_text.strip())} chars)"

        # Filter 2: Date range
        pub_date_str = article.get("published_at") or article.get("pubDate") or ""
        article_date = self._parse_date(pub_date_str)

        if self.from_date and article_date:
            if article_date < self.from_date:
                return False, f"before_from_date ({article_date.isoformat()})"

        if self.to_date and article_date:
            if article_date > self.to_date:
                return False, f"after_to_date ({article_date.isoformat()})"

        # Filter 3: Source whitelist/blacklist
        source = self._get_article_source(article)

        if self.sources_whitelist and source not in self.sources_whitelist:
            return False, f"source_not_in_whitelist ({source})"

        if self.sources_blacklist and source in self.sources_blacklist:
            return False, f"source_blacklisted ({source})"

        # Filter 4: Category filter
        if self.categories:
            cat = (article.get("category") or "").lower()
            if cat not in self.categories:
                return False, f"category_not_matched ({cat})"

        # Filter 5: Keyword filter (at least one keyword must match)
        if self.keywords:
            text = self._get_article_text(article)
            matches = [k for k in self.keywords if k in text]
            if not matches:
                return False, "no_keywords_matched"

        # Filter 6: Symbol filter (at least one symbol must appear)
        if self.symbols:
            text = self._get_article_text(article)
            found = [s for s in self.symbols if s in text]
            if not found:
                return False, "no_symbols_matched"

        return True, ""

    def filter(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply all active filters and return passing articles."""
        passed: list[dict[str, Any]] = []
        stats: dict[str, int] = {}

        for article in articles:
            ok, reason = self.passes(article)
            if ok:
                passed.append(article)
            else:
                stats[reason] = stats.get(reason, 0) + 1

        if stats:
            logger.info(
                "Filtering: %d passed, %d filtered out. Reasons: %s",
                len(passed),
                len(articles) - len(passed),
                dict(stats),
            )

        return passed

    def score_relevance(self, article: dict[str, Any]) -> float:
        """Score an article's relevance to stock market news (0.0 to 1.0).

        Higher score = more relevant to capital markets.
        """
        text = self._get_article_text(article)
        if not text:
            return 0.0

        # Count economy keyword matches
        matches = sum(1 for k in self._default_economy_keywords if k in text)

        # Normalize: typical relevant article has ~3-5 keyword matches
        score = min(1.0, matches / 5.0)

        # Bonus for having a stock symbol mention
        if self.symbols:
            symbol_matches = sum(1 for s in self.symbols if s in text)
            score = min(1.0, score + symbol_matches * 0.1)

        return score
