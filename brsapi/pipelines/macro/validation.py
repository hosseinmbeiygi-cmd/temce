from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

MACRO_REQUIRED = ["indicator"]
MACRO_IDEMPOTENT_FIELDS = ["indicator", "date", "category"]


class MacroValidator:
    def validate(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        for field in MACRO_REQUIRED:
            if not data.get(field):
                return Result.fail(f"Missing required field: {field}")
        value = data.get("value")
        if value is not None and isinstance(value, (int, float)) and (value < -1e12 or value > 1e12):
            return Result.fail(f"Value out of range: {value}")
        change_pct = data.get("change_pct")
        if change_pct is not None and isinstance(change_pct, (int, float)) and abs(change_pct) > 100:
            logger.warning("Large change_pct: %s for %s", change_pct, data.get("indicator"))
        return Result.ok(data)

    def is_duplicate(self, existing: list[dict[str, Any]], new_record: dict[str, Any]) -> bool:
        new_keys = {field: new_record.get(field) for field in MACRO_IDEMPOTENT_FIELDS if new_record.get(field)}
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
        logger.info("Validated %d/%d macro records", len(valid), len(records))
        return valid, errors
