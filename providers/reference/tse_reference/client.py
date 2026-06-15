from __future__ import annotations

from typing import Any

from core.config import settings
from core.result import Result
from providers.base.http_client import HttpClient

TSE_REFERENCE_BASE = "https://www.tsetmc.com/tsev2/data"


class TseReferenceClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(base_url=TSE_REFERENCE_BASE, timeout=settings.provider_default_timeout)

    async def get_instrument_list(self) -> Result[Any]:
        return await self.get("/InstIni.aspx")

    async def get_instrument_detail(self, ins_code: str) -> Result[Any]:
        return await self.get("/InstIni.aspx", params={"insCode": ins_code})

    async def get_shareholders(self, ins_code: str) -> Result[Any]:
        return await self.get("/ShareHolder.aspx", params={"insCode": ins_code})

    async def get_corporate_events(self, ins_code: str) -> Result[Any]:
        return await self.get("/CorporateEvent.aspx", params={"insCode": ins_code})
