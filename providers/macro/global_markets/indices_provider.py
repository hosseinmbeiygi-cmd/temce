from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


GLOBAL_INDICES = {
    "SPX": "S&P 500",
    "IXIC": "NASDAQ",
    "DJI": "Dow Jones",
    "N225": "Nikkei 225",
    "HSI": "Hang Seng",
    "FTSE": "FTSE 100",
    "DAX": "DAX 40",
    "CAC": "CAC 40",
    "SSEC": "Shanghai Composite",
    "KS11": "KOSPI",
}


class GlobalIndicesProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__(name="global_indices")
        self.client = HttpClient(base_url="https://api.example.com/global/indices")

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        if symbol:
            result = await self.client.get(f"/{symbol}")
        else:
            result = await self.client.get("")
        return result

    async def health(self) -> dict[str, Any]:
        result = await self.client.get("")
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
