from __future__ import annotations

from typing import Any

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)


def _storage_settings() -> dict[str, str]:
    """Resolve S3 config from ``STORAGE_*`` env vars (StorageSettings).

    Falls back to the top-level ``settings`` attributes if the dedicated
    storage settings are unset, so both config styles keep working.
    """
    try:
        from core.config.storage import StorageSettings

        s = StorageSettings()
    except Exception:
        s = None

    def pick(*names: str) -> str:
        for n in names:
            val = getattr(s, n, None) if s is not None else None
            if val:
                return str(val)
            val = getattr(settings, n, None)
            if val:
                return str(val)
        return ""

    return {
        "endpoint_url": pick("s3_endpoint_url"),
        "access_key": pick("s3_access_key"),
        "secret_key": pick("s3_secret_key"),
        "bucket": pick("s3_bucket"),
        "region": pick("s3_region"),
    }


class S3CompatibleStorage:
    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        region: str = "default",
    ):
        cfg = _storage_settings()
        self._endpoint = (endpoint_url or cfg["endpoint_url"] or "").rstrip("/")
        self._access_key = access_key or cfg["access_key"]
        self._secret_key = secret_key or cfg["secret_key"]
        self._bucket = bucket or cfg["bucket"] or "market-data"
        self._region = region if region != "default" else (cfg["region"] or "us-east-1")
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

    async def iter_files(self, pattern: str = "**/*") -> Any:
        """Yield object keys, compatible with ``RetentionManager``.

        ``pattern`` is accepted for interface parity with
        ``LocalStorage.iter_files``; S3 listing is prefix-based, so the
        pattern is applied as a simple suffix/contains filter when non-"*"
        glob-like strings are passed.
        """
        keys = await self.list(prefix="")
        if pattern in ("*", "**/*"):
            for k in keys:
                yield k
            return
        # Best-effort glob emulation: match keys containing the literal parts
        # of a simple pattern (e.g. "quotes/*" matches any key starting with
        # "quotes/").
        prefix_part = pattern.split("*")[0].rstrip("/")
        for k in keys:
            if prefix_part and not k.startswith(prefix_part + "/"):
                continue
            yield k

    async def stat(self, key: str) -> Result[Any]:
        """Return object metadata via a HEAD request.

        Compatible with ``RetentionManager``: Result containing
        ``{"modified": mtime_epoch, "size": bytes}``.
        """
        client = await self._get_client()
        url = f"/{self._bucket}/{key}"
        try:
            resp = await client.head(url)
            resp.raise_for_status()
            import email.utils

            modified = 0.0
            last_modified = resp.headers.get("Last-Modified")
            if last_modified:
                parsed = email.utils.parsedate_to_datetime(last_modified)
                modified = parsed.timestamp()
            size = int(resp.headers.get("Content-Length") or 0)
            return Result.ok({"size": size, "modified": modified})
        except httpx.HTTPError as e:
            return Result.fail(str(e))

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
