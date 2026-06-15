from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


POSITIVE_WORDS_FA = {"افزایش", "رشد", "سود", "بهبود", "صعود", "مثبت", "قوی", "عالی", "خوب", "امیدبخش"}
NEGATIVE_WORDS_FA = {"کاهش", "ضرر", "افت", "نزول", "منفی", "ضعیف", "بد", "وحشتناک", "نگران", "بحران"}
POSITIVE_WORDS_EN = {
    "increase",
    "growth",
    "profit",
    "improve",
    "rise",
    "positive",
    "strong",
    "excellent",
    "good",
    "bullish",
}
NEGATIVE_WORDS_EN = {
    "decrease",
    "loss",
    "decline",
    "drop",
    "negative",
    "weak",
    "bad",
    "terrible",
    "worry",
    "crisis",
    "bearish",
}


class SentimentLexicon:
    def __init__(self) -> None:
        self._positive: set[str] = set()
        self._negative: set[str] = set()
        self._scores: dict[str, float] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        for w in POSITIVE_WORDS_FA:
            self.add_positive(w, 0.5)
        for w in NEGATIVE_WORDS_FA:
            self.add_negative(w, -0.5)
        for w in POSITIVE_WORDS_EN:
            self.add_positive(w, 0.6)
        for w in NEGATIVE_WORDS_EN:
            self.add_negative(w, -0.6)

    def add_positive(self, word: str, score: float = 1.0) -> None:
        self._positive.add(word.lower())
        self._scores[word.lower()] = score

    def add_negative(self, word: str, score: float = -1.0) -> None:
        self._negative.add(word.lower())
        self._scores[word.lower()] = score

    def get_score(self, word: str) -> float:
        return self._scores.get(word.lower(), 0.0)

    def is_positive(self, word: str) -> bool:
        return word.lower() in self._positive

    def is_negative(self, word: str) -> bool:
        return word.lower() in self._negative

    def is_neutral(self, word: str) -> bool:
        w = word.lower()
        return w not in self._positive and w not in self._negative
