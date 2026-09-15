from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger
from providers.historical.tsetmc_historical.client import TsetmcHistoricalClient

logger = get_logger(__name__)


class TsetmcHistoricalHealth:
    def __init__(self, client: TsetmcHistoricalClient | None = None) -> None:
        self.client = client or TsetmcHistoricalClient()

    async def check(self) -> dict[str, Any]:
        try:
            result = await self.client.get_instrument_history("test", 1)
            return {
                "status": ProviderHealth.HEALTHY if result.success else ProviderHealth.DOWN,
                "message": "ok" if result.success else result.error,
                "latency_ms": 0.0,
            }
        except Exception as e:
            logger.error("TSETMC historical health check failed: %s", e)
            return {"status": ProviderHealth.DOWN, "message": str(e)}
