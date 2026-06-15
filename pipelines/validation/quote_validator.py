from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class QuoteValidator:
    REQUIRED_FIELDS = ["instrument_id", "price_close"]
    POSITIVE_FIELDS = ["price_close", "volume"]

    def validate(self, data: dict[str, Any]) -> bool:
        for field in self.REQUIRED_FIELDS:
            if field not in data or data[field] is None:
                logger.warning("Missing required field: %s", field)
                return False
        for field in self.POSITIVE_FIELDS:
            val = data.get(field, 0)
            if isinstance(val, (int, float)) and val < 0:
                logger.warning("Invalid negative %s: %s", field, val)
                return False
        return True
