from __future__ import annotations

from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class GlobalMarketsParser(ParserBase):
    def parse(self, raw_data: Any) -> list[dict[str, Any]]:
        if isinstance(raw_data, list):
            return raw_data
        if isinstance(raw_data, dict):
            if "data" in raw_data:
                return raw_data["data"]
            if "indices" in raw_data:
                return raw_data["indices"]
            return [raw_data]
        return []

    def validate(self, parsed: list[dict[str, Any]]) -> bool:
        return len(parsed) > 0
