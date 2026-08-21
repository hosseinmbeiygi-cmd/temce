from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

CODAL_REQUIRED = ["tracking_no"]
CODAL_IDEMPOTENT_FIELDS = ["tracking_no", "instrument_id"]


class CodalValidator:
    def validate(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        for field in CODAL_REQUIRED:
            if not data.get(field):
                return Result.fail(f"Missing required field: {field}")
        tracking_no = data.get("tracking_no")
        if isinstance(tracking_no, str) and not tracking_no.strip():
            return Result.fail("Empty tracking_no")
        title = data.get("title", "")
        if isinstance(title, str) and len(title) > 2000:
            logger.warning("Title too long, truncating: %s", title[:100])
            data["title"] = title[:2000]
        return Result.ok(data)

    def is_duplicate(self, existing: list[dict[str, Any]], new_record: dict[str, Any]) -> bool:
        new_keys = {field: new_record.get(field) for field in CODAL_IDEMPOTENT_FIELDS if new_record.get(field)}
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
        logger.info("Validated %d/%d codal records", len(valid), len(records))
        return valid, errors
