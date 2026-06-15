from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


INTEREST_RATES = ["Fed_Funds", "ECB", "BOE", "BOJ", "CBI"]


class GlobalRatesProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="global_rates")
        self.client = HttpClient(base_url="https://api.example.com/global/rates")

    async def fetch(self, rate: str | None = None, **kwargs: Any) -> Result[Any]:
        if rate:
            result = await self.client.get(f"/{rate}")
        else:
            result = await self.client.get("")
        return result

    async def health(self) -> dict[str, Any]:
        result = await self.client.get("")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
