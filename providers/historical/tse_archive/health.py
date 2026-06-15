from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger
from providers.historical.tse_archive.client import TseArchiveClient

logger = get_logger(__name__)


class TseArchiveHealth:
    def __init__(self, client: TseArchiveClient | None = None) -> None:
        self.client = client or TseArchiveClient()

    async def check(self) -> dict[str, Any]:
        try:
            result = await self.client.get_price_history("test", 1)
            return {
                "status": ProviderHealth.HEALTHY if result.success else ProviderHealth.DOWN,
                "message": "ok" if result.success else result.error,
            }
        except Exception as e:
            logger.error("TSE archive health check failed: %s", e)
            return {"status": ProviderHealth.DOWN, "message": str(e)}
