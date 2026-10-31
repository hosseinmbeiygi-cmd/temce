from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


# ── catalog-driven symbol extraction ─────────────────────────────────────
# Persian/Arabic spelling noise is folded before matching so a ticker written
# with Arabic ي/ك or non-Latin digits still resolves to the canonical catalog
# symbol. This mirrors ``services.news_tag_symbol_mapper.normalize_persian``
# on purpose: the providers layer must not import the services layer
# (ADR-0001).
_FOLD_MAP: dict[str, str] = {
    "ي": "ی",
    "ك": "ک",
    "ة": "ه",
    "ۀ": "ه",
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ؤ": "و",
    "ئ": "ی",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
}
_FOLD_RE = re.compile("[" + "".join(_FOLD_MAP) + "]")
_NOISE_RE = re.compile("[\u200c\u200d\u200e\u200f\u202a-\u202e\ufeff\u00a0]")

# ``#فولاد`` / ``$BTC`` — an explicit ticker quote is unambiguous, so the
# whole catalog (funds included) applies to it.
_CASHTAG_RE = re.compile(r"[#$]([^\s#$،,.;:!?؟()\[\]{}«»\"'…]+)")

# Fund tickers are ordinary Persian words (``آتش``، ``ارزش``، ``آس``) that
# dominate prose, so a *bare* fund mention is not trusted — only ``#``-quoted
# ones are. Even outside the fund sector one catalog ticker is far more often
# plain prose: ``کالا`` in «بورس کالا».
_FUND_SECTOR = "صندوق"
_BARE_DENY = frozenset({"کالا"})
_MIN_BARE_LEN = 2

# The catalog carries the same fund under both spellings (``آسامید`` and the
# Arabic ``آساميد``). They fold to one key, so the canonical Persian spelling
# must win instead of whichever entry the catalog happens to list first.
_ARABIC_SPELLING = ("ي", "ك")

# Cap on symbols attached to one article (audit stage 9: «cap نمادها»). A
# round-up or a long market report names dozens of tickers; tagging all of them
# makes the article follow (and notify on) the whole market, and each tag is a
# row in ``news_tags``. The first eight mentions by position are kept.
MAX_SYMBOLS_PER_ARTICLE = 8

_INDEX: tuple[dict[str, str], list[tuple[str, str]]] | None = None


def _fold_spelling(value: str) -> str:
    """Fold Persian/Arabic spelling noise and unify digits (casefolded)."""
    folded = _NOISE_RE.sub(" ", value)
    folded = _FOLD_RE.sub(lambda m: _FOLD_MAP[m.group(0)], folded)
    return " ".join(folded.split()).casefold()


def _prefer_canonical(current: str, candidate: str) -> str:
    """Return the Persian-canonical of two spellings of the same symbol."""
    current_arabic = any(ch in current for ch in _ARABIC_SPELLING)
    candidate_arabic = any(ch in candidate for ch in _ARABIC_SPELLING)
    if current_arabic and not candidate_arabic:
        return candidate
    return current


def _symbol_index() -> tuple[dict[str, str], list[tuple[str, str]]]:
    """``(folded symbol → symbol, bare candidates)`` — built once, then cached.

    Candidates are sorted longest-first so that ``کگل2`` wins over its
    ``کگل`` twin at the same position: a look-alike mention must never be
    truncated onto a shorter symbol.
    """
    global _INDEX  # noqa: PLW0603 — process-wide cache is intentional
    if _INDEX is not None:
        return _INDEX

    try:
        from domain.instruments import symbol_catalog

        rows = symbol_catalog.all_symbols()
    except Exception:  # noqa: BLE001 — tagging must degrade, never break ingest
        logger.warning("Symbol catalog unavailable — news symbol tagging degraded", exc_info=True)
        rows = []

    folded_to_symbol: dict[str, str] = {}
    candidates: list[tuple[str, str]] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip()
        folded = _fold_spelling(symbol)
        if not folded:
            continue
        existing = folded_to_symbol.get(folded)
        folded_to_symbol[folded] = symbol if existing is None else _prefer_canonical(existing, symbol)
        if (
            row.get("sector") != _FUND_SECTOR
            and len(symbol) >= _MIN_BARE_LEN
            and symbol not in _BARE_DENY
        ):
            candidates.append((folded, symbol))
    candidates.sort(key=lambda pair: (-len(pair[0]), pair[1]))
    _INDEX = (folded_to_symbol, candidates)
    return _INDEX


def _bare_position(haystack: str, needle: str) -> int | None:
    """Earliest mention of ``needle`` at a token boundary, or ``None``.

    Latin tickers need alphanumeric boundaries on both sides (``BTC`` must
    not match inside ``ABTCX``). Persian tickers need a boundary on the left
    and may be a word prefix, so ``فولاد`` still finds ``فولادمبارکه``.
    """
    if needle.isascii():
        match = re.search(rf"(?<![0-9a-z]){re.escape(needle)}(?![0-9a-z])", haystack)
        return match.start() if match else None
    start = haystack.find(needle)
    while start != -1:
        before = haystack[start - 1] if start else " "
        after_index = start + len(needle)
        after = haystack[after_index] if after_index < len(haystack) else " "
        if not before.isalnum() and not after.isalnum():
            return start
        start = haystack.find(needle, start + 1)
    return None


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
                desc = item.findtext(f"{ns}description", "") or item.findtext(f"{ns}summary", "") or item.findtext(f"{ns}content", "")
                link_elem = item.find(f"{ns}link")
                link = link_elem.get("href") or link_elem.text or "" if link_elem is not None else ""
                pub_date_elem = item.find(f"{ns}pubDate") or item.find(f"{ns}published") or item.find(f"{ns}updated")
                pub_date = pub_date_elem.text if pub_date_elem is not None and pub_date_elem.text else ""
                items.append({
                    "title": title or "",
                    "description": desc or "",
                    "link": link,
                    "published_at": self.normalize_date(pub_date),
                })
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
        """Extract market symbols mentioned in ``text``.

        Resolution is catalog-driven (``domain.instruments.symbol_catalog``),
        so coverage is the whole static catalog instead of a hard-coded list —
        and a returned symbol is always a real catalog ticker, never a guess.
        Returns symbols de-duplicated in order of first appearance.
        """
        if not text:
            return []
        folded_symbols, candidates = _symbol_index()
        folded_text = _fold_spelling(text)

        # position → symbol; the longest candidate wins at a shared position.
        hits: dict[int, str] = {}
        for match in _CASHTAG_RE.finditer(folded_text):
            symbol = folded_symbols.get(match.group(1))
            if symbol:
                hits.setdefault(match.start(), symbol)
        for needle, symbol in candidates:
            position = _bare_position(folded_text, needle)
            if position is not None:
                hits.setdefault(position, symbol)
        # Two mentions of the same ticker (or a bare + a ``#`` mention) are one
        # symbol: collapse by value, keeping first-appearance order, and cap the
        # result (MAX_SYMBOLS_PER_ARTICLE) so a market round-up does not tag
        # every ticker it lists.
        ordered: list[str] = []
        truncated = False
        for _, symbol in sorted(hits.items()):
            if symbol in ordered:
                continue
            if len(ordered) >= MAX_SYMBOLS_PER_ARTICLE:
                truncated = True
                break
            ordered.append(symbol)
        if truncated:
            logger.debug(
                "extract_symbols: capped at %d symbols", MAX_SYMBOLS_PER_ARTICLE
            )
        return ordered

    def normalize_date(self, date_str: str) -> str:
        """Normalize a date string to ISO 8601 UTC format.

        Handles common RSS/Atom date formats and returns ISO 8601 string.
        Falls back to the original string if parsing fails.
        """
        from datetime import datetime

        if not date_str or not date_str.strip():
            return datetime.now(UTC).isoformat()

        _formats = [
            "%a, %d %b %Y %H:%M:%S %z",   # RFC 2822 (standard RSS)
            "%a, %d %b %Y %H:%M:%S %Z",   # RFC 2822 with timezone name
            "%Y-%m-%dT%H:%M:%S%z",          # ISO 8601
            "%Y-%m-%dT%H:%M:%S.%f%z",       # ISO 8601 with microseconds
            "%Y-%m-%dT%H:%M:%S",            # ISO 8601 (naive)
            "%Y-%m-%d %H:%M:%S",            # Common database format
            "%Y/%m/%d",                      # Shamsi-like pattern (converted as-is)
            "%Y-%m-%d",                      # Simple date
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
