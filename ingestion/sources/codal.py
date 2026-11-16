from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from ingestion.http_client import HttpClient

from .base import DataSource, FetchResult, SourcePayload

logger = get_logger(__name__)

CODAL_BASE = "https://search.codal.ir/api/search/v2"


class CodalSource(DataSource):
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    @property
    def name(self) -> str:
        return "codal"

    async def fetch(self, context: dict[str, Any] | None = None) -> FetchResult:
        params: dict[str, str] = {
            "Audited": "true",
            "Length": "20",
            "search": "true",
        }
        raw = await self._http.fetch(CODAL_BASE, params=params)
        payload = SourcePayload(
            source=self.name,
            endpoint="/api/search/v2",
            raw_data=raw,
            content_type="application/json",
            fetch_time=datetime.now(UTC),
        )
        return FetchResult(payloads=[payload])

    async def health_check(self) -> bool:
        try:
            await self._http.fetch(CODAL_BASE, params={"Length": "1"}, method="HEAD")
            return True
        except Exception:
            return False
