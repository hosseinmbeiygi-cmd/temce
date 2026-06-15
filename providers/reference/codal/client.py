from __future__ import annotations

from typing import Any

from core.config import settings
from core.result import Result
from providers.base.http_client import HttpClient


class CodalClient(HttpClient):
    def __init__(self) -> None:
        super().__init__(
            base_url=settings.codal_base_url,
            timeout=settings.provider_default_timeout,
        )

    async def search_reports(self, query: str, page: int = 1, limit: int = 20) -> Result[Any]:
        return await self.get("/api/Search", params={"query": query, "page": page, "limit": limit})

    async def get_report(self, report_id: str) -> Result[Any]:
        return await self.get(f"/api/Report/{report_id}")

    async def get_company_reports(self, symbol: str, limit: int = 50) -> Result[Any]:
        return await self.get(f"/api/Company/{symbol}/Reports", params={"limit": limit})

    async def get_attachment(self, attachment_id: str) -> Result[Any]:
        return await self.get(f"/api/Attachment/{attachment_id}")

    async def get_letter(self, letter_id: str) -> Result[Any]:
        return await self.get(f"/api/Letter/{letter_id}")
