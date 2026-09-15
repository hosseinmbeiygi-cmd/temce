from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger

logger = get_logger(__name__)


class CodalHealth:
    async def check(self) -> dict[str, Any]:
        return {
            "status": ProviderHealth.HEALTHY,
            "message": "Codal provider ready",
        }
