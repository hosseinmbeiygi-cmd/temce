from __future__ import annotations

import re
from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class MarketWatchParser(ParserBase):
    def parse(self, raw_data: Any) -> dict[str, Any]:
        if isinstance(raw_data, dict):
            return raw_data
        if isinstance(raw_data, str):
            return self._parse_html(raw_data)
        return {}

    def _parse_html(self, html: str) -> dict[str, Any]:
        data: dict[str, Any] = {}
        price_match = re.search(r'<meta[^>]* itemprop="price"[^>]* content="([^"]+)"', html)
        if price_match:
            data["price"] = price_match.group(1)
        change_match = re.search(r'<meta[^>]* itemprop="priceChange"[^>]* content="([^"]+)"', html)
        if change_match:
            data["change"] = change_match.group(1)
        return data

    def validate(self, parsed: dict[str, Any]) -> bool:
        return len(parsed) > 0
