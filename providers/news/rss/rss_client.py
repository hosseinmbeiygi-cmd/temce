from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.http_client import HttpClient

logger = get_logger(__name__)


class RSSClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(timeout=15)

    async def fetch_feed(self, url: str) -> Result[Any]:
        result = await self.get(url)
        if result.success and hasattr(result.value, "text"):
            return Result.ok(result.value.text)
        return result
