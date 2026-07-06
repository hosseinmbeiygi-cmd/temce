from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


# Extended Persian sentiment word lists with morphological variants
POSITIVE_WORDS_FA = {
    "افزایش", "افزایشی", "افزایش‌یافت", "افزوده",
    "رشد", "رشدی", "رو‌به‌رشد",
    "سود", "سودآور", "سودده", "سوددهی",
    "بهبود", "بهبودی", "بهبوددهنده", "بهبود‌یافته",
    "صعود", "صعودی", "صعودکننده",
    "مثبت", "خوش‌بین", "خوش‌بینانه",
    "قوی", "قدرتمند", "تقویت",
    "عالی", "خوب", "مطلوب", "مناسب", "رضایت‌بخش",
    "امیدبخش", "امیدوار", "امیدوارانه",
    "توسعه", "پیشرفت", "موفق", "موفقیت",
    "رونق", "رونق‌یافتن",
    "جهش", "جهشی",
    "تنظیم", "بازگشت", "احیا",
    "سازنده", "آباد", "آبادانی",
}

NEGATIVE_WORDS_FA = {
    "کاهش", "کاهشی", "کاسته",
    "ضرر", "ضررده", "زیان", "زیان‌ده",
    "افت", "افتی", "سقوط",
    "نزول", "نزولی",
    "منفی", "بدبین", "بدبینانه",
    "ضعیف", "تضعیف", "ضعف",
    "بد", "نا‌مطلوب", "نامناسب",
    "وحشتناک", "فاجعه", "فاجعه‌بار",
    "نگران", "نگرانی", "نگران‌کننده",
    "بحران", "بحرانی", "درماندگی",
    "ورشکست", "ورشکستگی",
    "رکود", "رکودی",
    "تهدید", "خطر", "خطرناک", "پر‌خطر",
    "تحریم", "تحریمی",
    "تورم", "تورمی",
    "بی‌ثبات", "بی‌ثباتی",
    "عدم‌قطعیت", "مبهم",
    "اخلال", "مختل",
    "ناکارآمد", "ضعف",
}

POSITIVE_WORDS_EN = {
    "increase", "growth", "grow", "growing", "grew",
    "profit", "profitable", "profitability",
    "improve", "improvement", "improving", "improved",
    "rise", "rising", "rose", "gain", "gains",
    "positive", "optimistic", "optimism",
    "strong", "strength", "strengthen", "strengthening",
    "excellent", "outstanding", "remarkable",
    "good", "great", "favorable", "promising",
    "bullish", "rally", "rallying", "boom",
    "expansion", "expanding", "expand",
    "success", "successful", "succeed",
    "recovery", "recovering", "recovered",
    "upgrade", "upgraded", "beat", "beating",
    "surplus", "dividend", "opportunity", "innovation",
}

NEGATIVE_WORDS_EN = {
    "decrease", "decreasing", "decreased", "decline",
    "loss", "losses", "losing", "lost",
    "drop", "dropping", "dropped", "fall", "falling", "fell",
    "negative", "pessimistic", "pessimism",
    "weak", "weakness", "weaken", "weakening",
    "bad", "poor", "terrible", "dismal", "disappointing",
    "worry", "worries", "worrisome", "worrying",
    "crisis", "crash", "crashes", "collapse",
    "bearish", "downturn", "recession", "depression",
    "risk", "risky", "uncertainty", "volatile", "volatility",
    "sanction", "sanctions", "sanctioned",
    "inflation", "inflationary", "deficit", "debt",
    "bankrupt", "bankruptcy", "insolvent",
    "downgrade", "downgraded", "miss", "missed",
    "instability", "turmoil", "chaos", "disruption",
}


class SentimentLexicon:
    """Bilingual (Persian/English) sentiment lexicon with weighted scores."""

    def __init__(self) -> None:
        self._positive: set[str] = set()
        self._negative: set[str] = set()
        self._scores: dict[str, float] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default Persian and English sentiment word lists."""
        for w in POSITIVE_WORDS_FA:
            self.add_positive(w, 0.5)
        for w in NEGATIVE_WORDS_FA:
            self.add_negative(w, -0.5)
        for w in POSITIVE_WORDS_EN:
            self.add_positive(w, 0.6)
        for w in NEGATIVE_WORDS_EN:
            self.add_negative(w, -0.6)

    def add_positive(self, word: str, score: float = 1.0) -> None:
        """Add a positive word with an associated score."""
        self._positive.add(word.lower())
        self._scores[word.lower()] = score

    def add_negative(self, word: str, score: float = -1.0) -> None:
        """Add a negative word with an associated score."""
        self._negative.add(word.lower())
        self._scores[word.lower()] = score

    def get_score(self, word: str) -> float:
        """Get the sentiment score for a word. Returns 0.0 if unknown."""
        return self._scores.get(word.lower(), 0.0)

    def is_positive(self, word: str) -> bool:
        """Check if a word is positive."""
        return word.lower() in self._positive

    def is_negative(self, word: str) -> bool:
        """Check if a word is negative."""
        return word.lower() in self._negative

    def is_neutral(self, word: str) -> bool:
        """Check if a word is neither positive nor negative."""
        w = word.lower()
        return w not in self._positive and w not in self._negative

    @property
    def positive_count(self) -> int:
        """Number of positive words in the lexicon."""
        return len(self._positive)

    @property
    def negative_count(self) -> int:
        """Number of negative words in the lexicon."""
        return len(self._negative)
