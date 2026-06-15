from __future__ import annotations

from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class DomesticNewsParser(ParserBase):
    def parse(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "articles" in raw_data:
                return raw_data["articles"]
            if "data" in raw_data:
                return raw_data["data"]
            if "items" in raw_data:
                return raw_data["items"]
            return [raw_data]
        return []

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        return len(parsed) > 0
