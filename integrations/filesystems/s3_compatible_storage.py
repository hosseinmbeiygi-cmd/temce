from __future__ import annotations

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


class S3CompatibleStorage:
    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        region: str = "default",
    ):
        self._endpoint = (endpoint_url or "").rstrip("/")
        self._access_key = access_key or ""
        self._secret_key = secret_key or ""
        self._bucket = bucket or settings.s3_bucket or "market-data"
        self._region = region
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._endpoint, timeout=30.0)
        return self._client

    async def write(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Result[str]:
        client = await self._get_client()
        url = f"/{self._bucket}/{key}"
        headers = {"Content-Type": content_type, "Content-Length": str(len(data))}
        try:
            resp = await client.put(url, content=data, headers=headers)
            resp.raise_for_status()
            return Result.ok(key)
        except httpx.HTTPError as e:
            return Result.fail(str(e))

    async def read(self, key: str) -> Result[bytes]:
        client = await self._get_client()
        url = f"/{self._bucket}/{key}"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return Result.ok(resp.content)
        except httpx.HTTPError as e:
            return Result.fail(str(e))

    async def delete(self, key: str) -> Result[bool]:
        client = await self._get_client()
        url = f"/{self._bucket}/{key}"
        try:
            resp = await client.delete(url)
            resp.raise_for_status()
            return Result.ok(True)
        except httpx.HTTPError as e:
            return Result.fail(str(e))

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        url = f"/{self._bucket}/{key}"
        try:
            resp = await client.head(url)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def list(self, prefix: str = "") -> list[str]:
        client = await self._get_client()
        url = f"/{self._bucket}/?prefix={prefix}&list-type=2"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            import xml.etree.ElementTree as ET

            root = ET.fromstring(resp.text)
            ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
            keys = []
            for item in root.iter("s3:Key", ns):
                if item.text:
                    keys.append(item.text)
            return keys
        except (httpx.HTTPError, ET.ParseError):
            return []

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
