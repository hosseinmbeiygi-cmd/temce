from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger

logger = get_logger(__name__)


class WebSocketHealth:
    async def check(self) -> dict[str, Any]:
        return {
            "status": ProviderHealth.HEALTHY,
            "message": "WebSocket provider ready" if True else "WebSocket library not installed",
        }
