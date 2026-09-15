from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


INDUSTRIAL_METALS = ["copper", "aluminum", "zinc", "lead", "nickel", "tin", "steel"]


class IndustrialMetalsProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="industrial_metals")
        self.client = HttpClient(base_url="https://api.example.com/metals/industrial")

    async def fetch(self, metal: str | None = None, **kwargs: Any) -> Result[Any]:
        if metal:
            result = await self.client.get(f"/{metal}")
        else:
            result = await self.client.get("")
        return result

    async def health(self) -> dict[str, Any]:
        result = await self.client.get("")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
