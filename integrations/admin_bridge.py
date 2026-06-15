from __future__ import annotations

from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class AdminBridge:
    async def trigger_action(self, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        logger.info("Admin bridge action: %s", action)
        return {"action": action, "status": "processed"}

    async def get_status(self) -> dict[str, Any]:
        return {"status": "operational"}
