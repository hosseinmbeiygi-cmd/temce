from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class BrokerAPI:
    async def send_order(self, order: dict[str, Any]) -> dict[str, Any]:
        logger.info("Order sent (simulated): %s", order.get("symbol"))
        return {"status": "simulated", "order_id": "mock"}

    async def get_positions(self, account: str) -> list[dict[str, Any]]:
        return []

    async def get_orders(self, account: str) -> list[dict[str, Any]]:
        return []

    async def cancel_order(self, order_id: str) -> bool:
        return True
