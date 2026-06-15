from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class WebSocketParser(ParserBase):
    def parse(self, raw_data: Any) -> dict[str, Any]:
        if isinstance(raw_data, dict):
            return raw_data
        if isinstance(raw_data, str):
            try:
                return json.loads(raw_data)
            except json.JSONDecodeError:
                logger.warning("Failed to parse WebSocket message")
                return {}
        return {}

    def parse_quote(self, message: dict[str, Any]) -> dict[str, Any]:
        data = message.get("data", {})
        return {
            "symbol": message.get("symbol"),
            "last_price": data.get("last_price") or data.get("last"),
            "change": data.get("change"),
            "volume": data.get("volume"),
            "timestamp": message.get("timestamp"),
        }

    def validate(self, parsed: dict[str, Any]) -> bool:
        return len(parsed) > 0
