from __future__ import annotations

import json
from typing import Any

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class IndexClient:
    def __init__(self, base_url: str = "", api_key: str = ""):
        self._base_url = (base_url or "http://localhost:9200").rstrip("/")
        self._api_key = api_key or getattr(settings, "search_api_key", "")
        self._headers = {"Content-Type": "application/json"}
        if self._api_key:
            self._headers["Authorization"] = f"Bearer {self._api_key}"

    async def create_index(
        self, name: str, mappings: dict[str, Any] | None = None, settings: dict[str, Any] | None = None
    ) -> Result[bool]:
        body: dict[str, Any] = {}
        if mappings:
            body["mappings"] = mappings
        if settings:
            body["settings"] = settings
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=30.0) as client:
            try:
                resp = await client.put(f"/{name}", json=body)
                resp.raise_for_status()
                logger.info("Index created: %s", name)
                return Result.ok(True)
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def delete_index(self, name: str) -> Result[bool]:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=30.0) as client:
            try:
                resp = await client.delete(f"/{name}")
                resp.raise_for_status()
                logger.info("Index deleted: %s", name)
                return Result.ok(True)
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def index_exists(self, name: str) -> bool:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0) as client:
            try:
                resp = await client.head(f"/{name}")
                return resp.status_code == 200
            except httpx.HTTPError:
                return False

    async def index_document(self, index: str, doc_id: str, document: dict[str, Any]) -> Result[str]:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=30.0) as client:
            try:
                resp = await client.put(f"/{index}/_doc/{doc_id}", json=document)
                resp.raise_for_status()
                return Result.ok(doc_id)
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def bulk_index(
        self, index: str, documents: list[dict[str, Any]], id_field: str = "id"
    ) -> Result[dict[str, Any]]:
        lines: list[str] = []
        for doc in documents:
            doc_id = doc.get(id_field, "")
            action = json.dumps({"index": {"_index": index, "_id": doc_id}}, ensure_ascii=False)
            lines.append(action)
            lines.append(json.dumps(doc, ensure_ascii=False, default=str))
        body = "\n".join(lines) + "\n"
        async with httpx.AsyncClient(
            base_url=self._base_url, headers={**self._headers, "Content-Type": "application/x-ndjson"}, timeout=60.0
        ) as client:
            try:
                resp = await client.post("/_bulk", content=body)
                resp.raise_for_status()
                return Result.ok(resp.json())
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def update_document(self, index: str, doc_id: str, updates: dict[str, Any]) -> Result[bool]:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=30.0) as client:
            try:
                resp = await client.post(f"/{index}/_update/{doc_id}", json={"doc": updates})
                resp.raise_for_status()
                return Result.ok(True)
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def delete_document(self, index: str, doc_id: str) -> Result[bool]:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=30.0) as client:
            try:
                resp = await client.delete(f"/{index}/_doc/{doc_id}")
                resp.raise_for_status()
                return Result.ok(True)
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def get_mapping(self, index: str) -> Result[dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0) as client:
            try:
                resp = await client.get(f"/{index}/_mapping")
                resp.raise_for_status()
                return Result.ok(resp.json())
            except httpx.HTTPError as e:
                return Result.fail(str(e))
