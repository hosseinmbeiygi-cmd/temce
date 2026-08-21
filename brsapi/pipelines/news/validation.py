from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

NEWS_REQUIRED = ["title"]
NEWS_IDEMPOTENT_FIELDS = ["title", "source", "published_at"]


class NewsValidator:
    def validate(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        for field in NEWS_REQUIRED:
            if not data.get(field):
                return Result.fail(f"Missing required field: {field}")
        title = data.get("title", "")
        if isinstance(title, str) and len(title) < 5:
            return Result.fail(f"Title too short: '{title}'")
        if isinstance(title, str) and len(title) > 5000:
            logger.warning("Title too long, truncating: %s", title[:100])
            data["title"] = title[:5000]
        url = data.get("url", "")
        if url and isinstance(url, str) and not url.startswith(("http://", "https://")):
            return Result.fail(f"Invalid URL: {url}")
        return Result.ok(data)

    def is_duplicate(self, existing: list[dict[str, Any]], new_record: dict[str, Any]) -> bool:
        new_keys = {field: new_record.get(field) for field in NEWS_IDEMPOTENT_FIELDS if new_record.get(field)}
        for record in existing:
            match = all(record.get(field) == value for field, value in new_keys.items())
            if match:
                return True
        return False

    def validate_batch(self, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        valid, errors = [], []
        for record in records:
            result = self.validate(record)
            if result.success:
                valid.append(record)
            else:
                errors.append(result.error or "validation failed")
        logger.info("Validated %d/%d news records", len(valid), len(records))
        return valid, errors
