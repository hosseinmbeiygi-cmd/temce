from __future__ import annotations

import hashlib
import re
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class NewsDeduplicator:
    """Deduplicate news articles using multiple similarity heuristics.

    Uses three levels of deduplication:
    1. Exact URL match — same URL = duplicate (fastest)
    2. Title hash — normalized title hash match (handles minor formatting diffs)
    3. Content similarity — first 200 chars hash (for articles with different URLs/titles)
    """

    def __init__(self, ttl_seconds: float = 86400.0) -> None:
        self._urls: dict[str, float] = {}
        self._title_hashes: dict[str, float] = {}
        self._content_hashes: dict[str, float] = {}
        self._ttl = ttl_seconds
        self._duplicates_removed: int = 0

    def _normalize_title(self, title: str) -> str:
        """Normalize a title for comparison: lowercase, strip punctuation, collapse whitespace."""
        t = title.lower().strip()
        t = re.sub(r"[^\w\s\u0600-\u06FF\u200C\u200D]", " ", t)  # preserve Persian + ZWNJ
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    def _hash(self, text: str) -> str:
        """Fast SHA-256 hash of a string."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _expire(self) -> None:
        """Remove expired entries from all caches."""
        import time

        now = time.monotonic()
        for store in (self._urls, self._title_hashes, self._content_hashes):
            expired = [k for k, expires in store.items() if now >= expires]
            for k in expired:
                del store[k]

    def is_duplicate(self, article: dict[str, Any]) -> bool:
        """Check if an article is a duplicate of a previously-seen one.

        Returns True if duplicate, False if new.
        """
        import time

        self._expire()
        now = time.monotonic()

        # Level 1: Exact URL match
        url = (article.get("link") or "").strip()
        if url and url in self._urls:
            self._duplicates_removed += 1
            return True

        # Level 2: Normalized title hash
        title = (article.get("title") or "").strip()
        if title:
            title_hash = self._hash(self._normalize_title(title))
            if title_hash in self._title_hashes:
                self._duplicates_removed += 1
                return True

        # Level 3: Content prefix hash (first 200 chars)
        desc = (article.get("description") or article.get("content") or "").strip()
        if len(desc) > 50:
            content_hash = self._hash(desc[:200])
            if content_hash in self._content_hashes:
                self._duplicates_removed += 1
                return True

        # Not a duplicate — record it
        if url:
            self._urls[url] = now + self._ttl
        if title:
            self._title_hashes[self._hash(self._normalize_title(title))] = now + self._ttl
        if len(desc) > 50:
            self._content_hashes[self._hash(desc[:200])] = now + self._ttl

        return False

    def deduplicate(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter a list of article dicts, removing duplicates."""
        before = len(articles)
        result = [a for a in articles if not self.is_duplicate(a)]
        removed = before - len(result)
        if removed:
            logger.info("Deduplication: removed %d/%d duplicate articles", removed, before)
        return result

    @property
    def duplicates_removed(self) -> int:
        """Total number of duplicates removed across all batches."""
        return self._duplicates_removed

    def reset(self) -> None:
        """Clear all caches and counters."""
        self._urls.clear()
        self._title_hashes.clear()
        self._content_hashes.clear()
        self._duplicates_removed = 0
