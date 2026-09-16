from __future__ import annotations

import contextlib
import json
from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class CodalParser(ParserBase):
    def parse(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "data" in raw_data:
                return raw_data["data"]
            if "reports" in raw_data:
                return raw_data["reports"]
            if "items" in raw_data:
                return raw_data["items"]
            return [raw_data]
        if isinstance(raw_data, str):
            with contextlib.suppress(json.JSONDecodeError):
                data = json.loads(raw_data)
                return self.parse(data)
        return []

    def parse_report_detail(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": raw.get("id") or raw.get("reportId"),
            "symbol": raw.get("symbol") or raw.get("symbol"),
            "company": raw.get("company") or raw.get("companyName"),
            "report_type": raw.get("reportType") or raw.get("type"),
            "period": raw.get("period"),
            "year": raw.get("year") or raw.get("fiscalYear"),
            "publish_date": raw.get("publishDate") or raw.get("pubDate"),
            "title": raw.get("title"),
        }

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        return len(parsed) > 0
