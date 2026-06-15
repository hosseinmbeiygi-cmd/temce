from __future__ import annotations

import math
from typing import Any

from core.logging import get_logger
from providers.news.sentiment.lexicon import SentimentLexicon

logger = get_logger(__name__)


class SentimentScorer:
    def score(self, tokens: list[str], lexicon: SentimentLexicon) -> dict[str, Any]:
        if not tokens:
            return {"sentiment": "neutral", "compound": 0.0, "positive": 0.0, "negative": 0.0, "neutral": 1.0}

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

        compound = total_score / math.sqrt(total_score**2 + 15) if total_score != 0 else 0.0

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
