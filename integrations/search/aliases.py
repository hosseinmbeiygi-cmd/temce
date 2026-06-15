from __future__ import annotations

from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class AliasManager:
    def __init__(self, base_url: str = ""):
        self._base_url = (base_url or "http://localhost:9200").rstrip("/")
        self._headers = {"Content-Type": "application/json"}

    async def add_alias(self, index: str, alias: str) -> Result[bool]:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0) as client:
            try:
                resp = await client.put(f"/{index}/_alias/{alias}")
                resp.raise_for_status()
                logger.info("Alias %s -> %s added", alias, index)
                return Result.ok(True)
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def remove_alias(self, index: str, alias: str) -> Result[bool]:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0) as client:
            try:
                resp = await client.delete(f"/{index}/_alias/{alias}")
                resp.raise_for_status()
                logger.info("Alias %s removed from %s", alias, index)
                return Result.ok(True)
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def get_aliases(self, index: str | None = None) -> Result[dict[str, Any]]:
        url = f"/{index}/_alias" if index else "/_alias"
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return Result.ok(resp.json())
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def swap_alias(self, alias: str, new_index: str, old_index: str) -> Result[bool]:
        actions = [
            {"remove": {"index": old_index, "alias": alias}},
            {"add": {"index": new_index, "alias": alias}},
        ]
        body = {"actions": actions}
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0) as client:
            try:
                resp = await client.post("/_aliases", json=body)
                resp.raise_for_status()
                logger.info("Alias %s swapped: %s -> %s", alias, old_index, new_index)
                return Result.ok(True)
            except httpx.HTTPError as e:
                return Result.fail(str(e))

    async def alias_exists(self, alias: str) -> bool:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=10.0) as client:
            try:
                resp = await client.head(f"/_alias/{alias}")
                return resp.status_code == 200
            except httpx.HTTPError:
                return False

    async def list_aliases_for_index(self, index: str) -> list[str]:
        result = await self.get_aliases(index)
        if result.success and result.value:
            index_data = result.value.get(index, {})
            return list(index_data.get("aliases", {}).keys())
        return []
