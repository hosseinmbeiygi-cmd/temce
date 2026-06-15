from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


BROKERAGE_FIELD_MAP = {
    "symbol": "symbol",
    "quantity": "quantity",
    "price": "price",
    "avg_price": "average_price",
    "last_price": "last_price",
    "side": "side",
    "status": "status",
    "total_value": "total_value",
    "cash": "cash_balance",
    "securities": "positions",
}


class BrokerageMapping:
    def __init__(self, field_map: dict[str, str] | None = None) -> None:
        self.field_map = field_map or BROKERAGE_FIELD_MAP

    def map(self, data: dict[str, Any]) -> dict[str, Any]:
        return {self.field_map.get(k, k): v for k, v in data.items()}

    def map_batch(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.map(row) for row in data]
