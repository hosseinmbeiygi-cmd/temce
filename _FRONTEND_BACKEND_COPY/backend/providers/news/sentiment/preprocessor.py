from __future__ import annotations

import re

from core.logging import get_logger

logger = get_logger(__name__)


# Persian stopwords — common words with no sentiment value
_PERSIAN_STOPWORDS: set[str] = {
    "و",
    "در",
    "به",
    "از",
    "که",
    "این",
    "را",
    "با",
    "بر",
    "برای",
    "تا",
    "هم",
    "نیز",
    "است",
    "بود",
    "شد",
    "شده",
    "خود",
    "آن",
    "اگر",
    "هر",
    "چند",
    "چه",
    "اما",
    "یا",
    "بی",
    "جز",
    "زیر",
    "بیش",
    "پس",
    "پیش",
    "بسیار",
    "همه",
    "دارد",
    "ها",
    "های",
    "می",
    "شود",
    "کرد",
    "یکی",
    "دو",
    "سه",
    "نه",
    "تنها",
    "فقط",
    "البته",
    "هنوز",
    "اکنون",
}

_ENGLISH_STOPWORDS: set[str] = {
    "and",
    "the",
    "to",
    "is",
    "in",
    "it",
    "of",
    "a",
    "an",
    "for",
    "on",
    "with",
    "as",
    "at",
    "by",
    "or",
    "be",
    "this",
    "that",
    "from",
    "but",
    "not",
    "are",
    "was",
    "were",
    "been",
    "has",
    "had",
    "have",
    "its",
    "will",
    "would",
    "could",
    "should",
    "can",
    "do",
    "does",
    "did",
    "so",
    "if",
    "than",
    "then",
    "no",
    "about",
    "up",
}


class TextPreprocessor:
    """Preprocesses text for sentiment analysis with Persian/English support.

    Handles URL removal, HTML stripping, punctuation normalization,
    Persian-specific cleaning (preserving ZWNJ / half-space), and tokenization.
    """

    def __init__(self) -> None:
        self._url_pattern = re.compile(r"https?://\S+|www\.\S+")
        self._html_pattern = re.compile(r"<[^>]+>")
        # Preserve ZWNJ (U+200C) and ZWJ (U+200D) for proper Persian text processing
        self._punctuation = re.compile(r"[^\w\s\u200C\u200D]")
        self._whitespace = re.compile(r"\s+")
        # Persian Unicode range + ZWNJ (U+200C) + ZWJ (U+200D) + Arabic characters
        self._persian_clean = re.compile(r"[^\u0600-\u06FF\u200C\u200D\w\s]")

    def clean(self, text: str) -> str:
        """Clean text: remove URLs, HTML, normalize punctuation and whitespace."""
        text = self._url_pattern.sub("", text)
        text = self._html_pattern.sub("", text)
        text = self._punctuation.sub(" ", text)
        text = self._persian_clean.sub(" ", text)
        text = self._whitespace.sub(" ", text)
        return text.strip().lower()

    def tokenize(self, text: str) -> list[str]:
        """Tokenize Persian/English text preserving ZWNJ (half-space)."""
        return [t for t in text.split() if len(t) > 1]

    def remove_stopwords(self, tokens: list[str], stopwords: set[str] | None = None) -> list[str]:
        """Remove stopwords from token list. Uses Persian + English defaults if none given."""
        if stopwords is None:
            stopwords = _ENGLISH_STOPWORDS | _PERSIAN_STOPWORDS
        return [t for t in tokens if t not in stopwords]
