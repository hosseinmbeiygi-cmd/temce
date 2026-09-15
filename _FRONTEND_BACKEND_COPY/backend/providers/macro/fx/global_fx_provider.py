from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


MAJOR_CURRENCY_PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD", "NZD_USD"]


class GlobalFXProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="global_fx")
        self.client = HttpClient(base_url="https://api.example.com/fx/global")

    async def fetch(self, pair: str | None = None, **kwargs: Any) -> Result[Any]:
        if pair:
            result = await self.client.get(f"/{pair}")
        else:
            result = await self.client.get("")
        return result

    async def health(self) -> dict[str, Any]:
        result = await self.client.get("")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
