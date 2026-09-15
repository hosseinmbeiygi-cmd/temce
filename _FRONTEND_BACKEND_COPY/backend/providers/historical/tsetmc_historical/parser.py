from __future__ import annotations

from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class TsetmcHistoricalParser(ParserBase):
    def parse(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "data" in raw_data:
                return raw_data["data"]
            if "records" in raw_data:
                return raw_data["records"]
            return [raw_data]
        return []

    def parse_daily(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "date": raw.get("date") or raw.get("d"),
            "open": raw.get("open") or raw.get("o"),
            "high": raw.get("high") or raw.get("h"),
            "low": raw.get("low") or raw.get("l"),
            "close": raw.get("close") or raw.get("c"),
            "volume": raw.get("volume") or raw.get("v"),
            "value": raw.get("value") or raw.get("vl"),
            "count": raw.get("count") or raw.get("n"),
        }

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        return len(parsed) > 0
