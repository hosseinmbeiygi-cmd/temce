from __future__ import annotations

from typing import Any

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class QueryClient:
    def __init__(self, base_url: str = "", api_key: str = ""):
        self._base_url = (base_url or "http://localhost:9200").rstrip("/")
        self._api_key = api_key or getattr(settings, "search_api_key", "")
        self._headers = {"Content-Type": "application/json"}
        if self._api_key:
            self._headers["Authorization"] = f"Bearer {self._api_key}"

    async def search(self, index: str, query: dict[str, Any], size: int = 20, from_: int = 0) -> Result[dict[str, Any]]:
        body = {"query": query, "size": size, "from": from_}
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=30.0) as client:
            try:
                resp = await client.post(f"/{index}/_search", json=body)
                resp.raise_for_status()
                return Result.ok(resp.json())
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def search_by_field(self, index: str, field: str, value: Any, size: int = 20) -> Result[dict[str, Any]]:
        query = {"term": {field: value}}
        return await self.search(index, query, size=size)

    async def search_by_text(
        self, index: str, text: str, fields: list[str] | None = None, size: int = 20
    ) -> Result[dict[str, Any]]:
        search_fields = fields or ["name", "symbol", "description"]
        query = {"multi_match": {"query": text, "fields": search_fields}}
        return await self.search(index, query, size=size)

    async def suggest(self, index: str, field: str, prefix: str, size: int = 5) -> Result[dict[str, Any]]:
        body = {"suggest": {"suggestion": {"prefix": prefix, "completion": {"field": field, "size": size}}}}
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0) as client:
            try:
                resp = await client.post(f"/{index}/_search", json=body)
                resp.raise_for_status()
                return Result.ok(resp.json())
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def count(self, index: str, query: dict[str, Any] | None = None) -> Result[int]:
        body = {"query": query} if query else {}
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0) as client:
            try:
                resp = await client.post(f"/{index}/_count", json=body)
                resp.raise_for_status()
                return Result.ok(resp.json().get("count", 0))
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def scroll(
        self, index: str, query: dict[str, Any], scroll: str = "2m", size: int = 1000
    ) -> Result[list[dict[str, Any]]]:
        body = {"query": query, "size": size}
        results: list[dict[str, Any]] = []
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=60.0) as client:
            try:
                resp = await client.post(f"/{index}/_search?scroll={scroll}", json=body)
                resp.raise_for_status()
                data = resp.json()
                scroll_id = data.get("_scroll_id", "")
                hits = data.get("hits", {}).get("hits", [])
                results.extend(h.get("_source", {}) for h in hits)
                while hits:
                    resp = await client.post("/_search/scroll", json={"scroll": scroll, "scroll_id": scroll_id})
                    resp.raise_for_status()
                    data = resp.json()
                    scroll_id = data.get("_scroll_id", "")
                    hits = data.get("hits", {}).get("hits", [])
                    results.extend(h.get("_source", {}) for h in hits)
                return Result.ok(results)
            except httpx.HTTPError as e:
                return Result.fail(str(e))
