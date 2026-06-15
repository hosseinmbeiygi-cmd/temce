from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger
from providers.base.parser_base import ParserBase

logger = get_logger(__name__)


class TsetmcParser(ParserBase):
    def parse(self, raw_data: Any) -> dict[str, Any]:
        if isinstance(raw_data, dict):
            return raw_data
        if isinstance(raw_data, str):
            try:
                data = json.loads(raw_data)
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                logger.warning("Failed to parse TSETMC JSON")
                return {}
        return {}

    def parse_quote(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "insCode": raw.get("insCode"),
            "symbol": raw.get("symbol") or raw.get("lVal18AFC"),
            "name": raw.get("name") or raw.get("lVal30"),
            "open": raw.get("open") or raw.get("pDrCotVal"),
            "high": raw.get("high") or raw.get("pHajCotVal"),
            "low": raw.get("low") or raw.get("pPminCotVal"),
            "close": raw.get("close") or raw.get("pCotVal"),
            "last": raw.get("last") or raw.get("pCotVal"),
            "volume": raw.get("volume") or raw.get("qTotTran5J"),
            "value": raw.get("value") or raw.get("qTotCap"),
            "count": raw.get("count") or raw.get("zTotTran"),
            "yesterday": raw.get("yesterday") or raw.get("pYCotVal"),
            "eps": raw.get("eps") or raw.get("eps"),
            "pe": raw.get("pe") or raw.get("pe"),
        }

    def validate(self, parsed: dict[str, Any]) -> bool:
        return len(parsed) > 0
