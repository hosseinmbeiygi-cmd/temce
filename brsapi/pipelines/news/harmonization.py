from __future__ import annotations

from typing import Any

from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)

NEWS_FIELD_MAP = {
    "title": "title",
    "summary": "summary",
    "body": "body",
    "url": "url",
    "source": "source",
    "author": "author",
    "published_at": "published_at",
    "category": "category",
    "tags": "tags",
    "symbol": "symbol",
    "sentiment": "sentiment",
    "sentiment_score": "sentiment_score",
}

SOURCE_NORMALIZE = {
    "tgju": "tgju",
    "tse": "tse",
    "ils": "iranianscm",
    "bourse": "bourse",
    "eneghar": "eneghar",
    "shafaqna": "shafaqna",
    "mehr": "mehr",
    "isna": "isna",
    "irna": "irna",
}


class NewsHarmonizer:
    def harmonize(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {"id": new_id("news")}
        for raw_key, value in raw.items():
            key = NEWS_FIELD_MAP.get(raw_key, raw_key)
            normalized[key] = value
        raw_source = normalized.get("source", "")
        normalized["source"] = SOURCE_NORMALIZE.get(raw_source, raw_source)
        if isinstance(normalized.get("tags"), str):
            normalized["tags"] = [t.strip() for t in normalized["tags"].split(",") if t.strip()]
        normalized.setdefault("source", "unknown")
        normalized.setdefault("extra", {})
        logger.debug("Harmonized news: %s", normalized.get("title", "?")[:60])
        return normalized

    def harmonize_batch(self, raw_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.harmonize(raw) for raw in raw_list]
