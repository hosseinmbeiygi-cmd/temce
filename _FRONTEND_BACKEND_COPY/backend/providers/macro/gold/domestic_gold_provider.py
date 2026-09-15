from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


IRANIAN_GOLD_TYPES = ["bahar_azadi", "nim_azadi", "rob_azadi", "gerami", "gold_coin", "gold_ingot"]


class DomesticGoldProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="domestic_gold")
        self.client = HttpClient(base_url="https://api.example.com/gold/domestic")

    async def fetch(self, gold_type: str | None = None, **kwargs: Any) -> Result[Any]:
        if gold_type:
            result = await self.client.get(f"/{gold_type}")
        else:
            result = await self.client.get("")
        return result

    async def health(self) -> dict[str, Any]:
        result = await self.client.get("")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
