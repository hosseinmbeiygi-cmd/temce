from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class BacktestValidator:
    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if not config.get("strategy"):
            errors.append("Missing strategy")
        if not config.get("start_date"):
            errors.append("Missing start_date")
        if not config.get("end_date"):
            errors.append("Missing end_date")
        return errors

    def validate_results(self, result: Any) -> list[str]:
        warnings = []
        if result is None:
            warnings.append("No results returned")
        return warnings
