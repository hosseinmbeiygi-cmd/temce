from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class TseRealtimeParser(ParserBase):
    def parse(self, raw_data: Any) -> dict[str, Any]:
        if isinstance(raw_data, dict):
            return raw_data
        if isinstance(raw_data, str):
            try:
                return json.loads(raw_data)
            except json.JSONDecodeError:
                logger.warning("Failed to parse TSE JSON")
                return {}
        return {}

    def parse_list(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "data" in raw_data:
                return raw_data["data"]
            if "items" in raw_data:
                return raw_data["items"]
            return [raw_data]
        if isinstance(raw_data, str):
            try:
                data = json.loads(raw_data)
                return data if isinstance(data, list) else [data]
            except json.JSONDecodeError:
                return []
        return []

    def validate(self, parsed: dict[str, Any]) -> bool:
        return len(parsed) > 0
