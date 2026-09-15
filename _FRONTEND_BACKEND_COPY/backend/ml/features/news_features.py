from __future__ import annotations

from typing import Any


class NewsFeatures:
    def compute(self, news_items: list[dict[str, Any]]) -> dict[str, float]:
        return {"sentiment_score": 0.0, "mention_count": 0, "novelty_score": 0.0, "urgency": 0.0}
