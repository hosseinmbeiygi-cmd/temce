from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


GLOBAL_GOLD_BENCHMARKS = ["XAU_USD", "XAU_EUR", "XAG_USD", "XPT_USD", "XPD_USD"]


class GlobalGoldProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="global_gold")
        self.client = HttpClient(base_url="https://api.example.com/gold/global")

    async def fetch(self, benchmark: str | None = None, **kwargs: Any) -> Result[Any]:
        if benchmark:
            result = await self.client.get(f"/{benchmark}")
        else:
            result = await self.client.get("")
        return result

    async def health(self) -> dict[str, Any]:
        result = await self.client.get("")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
