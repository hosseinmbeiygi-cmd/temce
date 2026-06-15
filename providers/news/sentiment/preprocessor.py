from __future__ import annotations

import re

from core.logging import get_logger

logger = get_logger(__name__)


class TextPreprocessor:
    def __init__(self) -> None:
        self._url_pattern = re.compile(r"https?://\S+|www\.\S+")
        self._html_pattern = re.compile(r"<[^>]+>")
        self._punctuation = re.compile(r"[^\w\s]")
        self._whitespace = re.compile(r"\s+")
        self._persian_clean = re.compile(r"[^\u0600-\u06FF\w\s]")

    def clean(self, text: str) -> str:
        text = self._url_pattern.sub("", text)
        text = self._html_pattern.sub("", text)
        text = self._punctuation.sub(" ", text)
        text = self._persian_clean.sub(" ", text)
        text = self._whitespace.sub(" ", text)
        return text.strip().lower()

    def tokenize(self, text: str) -> list[str]:
        return [t for t in text.split() if len(t) > 1]

    def remove_stopwords(self, tokens: list[str], stopwords: set[str] | None = None) -> list[str]:
        if stopwords is None:
            stopwords = {"and", "the", "to", "is", "in", "it", "of", "a", "an", "for", "on", "with", "as", "at", "by"}
        return [t for t in tokens if t not in stopwords]
