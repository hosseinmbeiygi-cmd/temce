from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


class ElectricityProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="electricity")
        self.client = HttpClient(base_url="https://api.example.com/energy/electricity")

    async def fetch(self, market: str | None = None, **kwargs: Any) -> Result[Any]:
        if market:
            result = await self.client.get(f"/{market}")
        else:
            result = await self.client.get("")
        return result

    async def health(self) -> dict[str, Any]:
        result = await self.client.get("")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
