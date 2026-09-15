from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


TSE_REFERENCE_FIELD_MAP = {
    "insCode": "instrument_code",
    "symbol": "symbol",
    "name": "name",
    "market": "market",
    "group": "sector_group",
    "eps": "eps",
    "shares": "total_shares",
    "base_volume": "base_volume",
    "cSecVal": "market_code",
    "cGroup": "sector_code",
    "lVal18AFC": "symbol",
    "lVal30": "name",
}


class TseReferenceMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or TSE_REFERENCE_FIELD_MAP

    def map(self, data: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in data.items()}

    def map_batch(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map(row) for row in data]
