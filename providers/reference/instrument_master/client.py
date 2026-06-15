from __future__ import annotations

from typing import Any

from core.config import settings
from core.result import Result
from providers.base.http_client import HttpClient


class InstrumentMasterClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(
            base_url=settings.tsetmc_base_url,
            timeout=settings.provider_default_timeout,
        )

    async def get_all_instruments(self) -> Result[Any]:
        return await self.get("/api/Instrument")

    async def get_instrument_detail(self, ins_code: str) -> Result[Any]:
        return await self.get(f"/api/Instrument/{ins_code}")

    async def search_instruments(self, query: str) -> Result[Any]:
        return await self.get("/api/Instrument/Search", params={"q": query})
