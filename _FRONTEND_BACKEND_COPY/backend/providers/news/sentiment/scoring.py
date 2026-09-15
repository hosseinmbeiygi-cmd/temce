from __future__ import annotations

import math
from typing import Any

from core.logging import get_logger
from providers.news.sentiment.lexicon import SentimentLexicon

logger = get_logger(__name__)


class SentimentScorer:
    """Computes compound sentiment scores using VADER-like normalization."""

    # Alpha constant for score normalization (VADER uses 15)
    _ALPHA: float = 15.0

    def score(self, tokens: list[str], lexicon: SentimentLexicon) -> dict[str, Any]:
        """Score a list of tokens using the provided lexicon.

        Returns a dict with sentiment label, compound score, and ratio breakdown.
        """
        if not tokens:
            return {
                "sentiment": "neutral",
                "compound": 0.0,
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 1.0,
            }

        total_score = 0.0
        pos_count = 0
        neg_count = 0
        neu_count = 0

        for token in tokens:
            score = lexicon.get_score(token)
            if score > 0:
                pos_count += 1
                total_score += score
            elif score < 0:
                neg_count += 1
                total_score += score
            else:
                neu_count += 1

        n = len(tokens)
        positive_ratio = pos_count / n
        negative_ratio = neg_count / n
        neutral_ratio = neu_count / n

        # VADER-style normalization: compound = x / sqrt(x² + alpha)
        compound = total_score / math.sqrt(total_score * total_score + self._ALPHA) if total_score != 0 else 0.0

        if compound >= 0.05:
            sentiment = "positive"
        elif compound <= -0.05:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "sentiment": sentiment,
            "compound": round(compound, 4),
            "positive": round(positive_ratio, 4),
            "negative": round(negative_ratio, 4),
            "neutral": round(neutral_ratio, 4),
        }
