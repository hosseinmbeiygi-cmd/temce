from __future__ import annotations

from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class FundParser(ParserBase):
    def parse(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "data" in raw_data:
                data = raw_data["data"]
                return data if isinstance(data, list) else [data]
            if "funds" in raw_data:
                return raw_data["funds"]
            return [raw_data]
        if isinstance(raw_data, str):
            return self._parse_json_str(raw_data)
        return []

    def parse_nav(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "nav_history" in raw_data:
                return raw_data["nav_history"]
            if "data" in raw_data:
                data = raw_data["data"]
                return data if isinstance(data, list) else [data]
            return [raw_data]
        return []

    def parse_holdings(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "holdings" in raw_data:
                return raw_data["holdings"]
            if "data" in raw_data:
                data = raw_data["data"]
                return data if isinstance(data, list) else [data]
            return [raw_data]
        return []

    def _parse_json_str(self, content: str) -> list[dict[str, Any]]:
        import json

        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                if "data" in data:
                    inner = data["data"]
                    return inner if isinstance(inner, list) else [inner]
                return [data]
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse fund JSON: %s", e)
        return []

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        return len(parsed) > 0
