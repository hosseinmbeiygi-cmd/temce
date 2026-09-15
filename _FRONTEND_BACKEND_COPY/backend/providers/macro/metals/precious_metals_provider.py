from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


PRECIOUS_METALS = ["gold", "silver", "platinum", "palladium", "rhodium"]


class PreciousMetalsProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="precious_metals")
        self.client = HttpClient(base_url="https://api.example.com/metals/precious")

    async def fetch(self, metal: str | None = None, **kwargs: Any) -> Result[Any]:
        if metal:
            result = await self.client.get(f"/{metal}")
        else:
            result = await self.client.get("")
        return result

    async def health(self) -> dict[str, Any]:
        result = await self.client.get("")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
