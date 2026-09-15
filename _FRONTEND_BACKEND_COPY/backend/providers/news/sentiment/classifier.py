from __future__ import annotations

from typing import Any

from core.logging import get_logger
from providers.news.sentiment.lexicon import SentimentLexicon
from providers.news.sentiment.preprocessor import TextPreprocessor
from providers.news.sentiment.scoring import SentimentScorer

logger = get_logger(__name__)


class SentimentClassifier:
    def __init__(
        self,
        lexicon: SentimentLexicon | None = None,
        preprocessor: TextPreprocessor | None = None,
        scorer: SentimentScorer | None = None,
    ) -> None:
        self.lexicon = lexicon or SentimentLexicon()
        self.preprocessor = preprocessor or TextPreprocessor()
        self.scorer = scorer or SentimentScorer()

    def classify(self, text: str) -> dict[str, Any]:
        cleaned = self.preprocessor.clean(text)
        tokens = self.preprocessor.tokenize(cleaned)
        scores = self.scorer.score(tokens, self.lexicon)
        return {
            "sentiment": scores["sentiment"],
            "compound": scores["compound"],
            "positive": scores["positive"],
            "negative": scores["negative"],
            "neutral": scores["neutral"],
            "text_length": len(text),
            "tokens_count": len(tokens),
        }

    def classify_batch(self, texts: list[str]) -> list[dict[str, Any]]:
        return [self.classify(t) for t in texts]
