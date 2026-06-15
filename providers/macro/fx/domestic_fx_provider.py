from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


IRANIAN_CURRENCY_PAIRS = ["USD_IRR", "EUR_IRR", "GBP_IRR", "TRY_IRR", "AED_IRR", "CNY_IRR"]


class DomesticFXProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="domestic_fx")
        self.client = HttpClient(base_url="https://api.example.com/fx/domestic")

    async def fetch(self, pair: str | None = None, **kwargs: Any) -> Result[Any]:
        if pair:
            result = await self.client.get(f"/{pair}")
        else:
            result = await self.client.get("")
        return result

    async def health(self) -> dict[str, Any]:
        result = await self.client.get("")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
