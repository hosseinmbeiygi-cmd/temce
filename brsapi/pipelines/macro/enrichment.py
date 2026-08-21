from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.time import now_iran

logger = get_logger(__name__)


class MacroEnricher:
    def enrich(self, data: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(data)
        value = enriched.get("value", 0)
        prev_value = enriched.get("previous_value")
        if prev_value and isinstance(prev_value, (int, float)) and prev_value != 0:
            enriched["period_change"] = round(value - prev_value, 4)
            enriched["period_change_pct"] = round((value - prev_value) / abs(prev_value) * 100, 4)
        else:
            enriched["period_change"] = 0.0
            enriched["period_change_pct"] = 0.0
        enriched["data_quality"] = self._assess_quality(enriched)
        enriched["series_length"] = enriched.get("series_length", 1)
        enriched["enriched_at"] = now_iran().isoformat()
        enriched.setdefault("extra", {})
        return enriched

    def _assess_quality(self, data: dict[str, Any]) -> str:
        issues = []
        if data.get("value") is None or data.get("value") == 0:
            issues.append("zero_or_null_value")
        if not data.get("date"):
            issues.append("missing_date")
        if not data.get("source"):
            issues.append("missing_source")
        if len(issues) == 0:
            return "complete"
        if len(issues) <= 1:
            return "acceptable"
        return "poor"

    def enrich_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.enrich(r) for r in records]
