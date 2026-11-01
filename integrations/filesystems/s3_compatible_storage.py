from __future__ import annotations

import asyncio
import io
import socket
from typing import Any

import httpx

from core.config import settings
from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

_S3_NOT_FOUND_CODES = {"NoSuchKey", "NoSuchObject", "NoSuchBucket", "XMinioInvalidObjectName"}
_S3_FORBIDDEN_CODES = {
    "AccessDenied",
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
    "InvalidToken",
    "ExpiredToken",
}


def _classify_s3_error(exc: Exception) -> str:
    """Map a MinIO/urllib3 exception onto a machine-readable failure code."""
    code = str(getattr(exc, "code", "") or "")
    if code in _S3_NOT_FOUND_CODES:
        return "not_found"
    if code in _S3_FORBIDDEN_CODES:
        return "forbidden"
    text = str(exc).lower()
    if isinstance(exc, (TimeoutError, socket.timeout)) or "timeout" in text or "timed out" in text:
        return "timeout"
    return "s3_error"


def _classify_http_status(status: int) -> str | None:
    """Map an HTTP status code onto a failure code (``None`` means success)."""
    if status == 404:
        return "not_found"
    if status in (401, 403):
        return "forbidden"
    if status in (408, 504):
        return "timeout"
    if status >= 500:
        return "server_error"
    if status >= 400:
        return "http_error"
    return None


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
        timeout: float = 30.0,
    ):
        cfg = _storage_settings()
        self._endpoint = (endpoint_url or cfg["endpoint_url"] or "").rstrip("/")
        self._access_key = access_key or cfg["access_key"]
        self._secret_key = secret_key or cfg["secret_key"]
        self._bucket = bucket or cfg["bucket"] or "market-data"
        self._region = region if region != "default" else (cfg["region"] or "us-east-1")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._minio: Any | None = None
        self._minio_initialized = False

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._endpoint, timeout=self._timeout)
        return self._client

    def _minio_client(self) -> Any | None:
        """Return a signed MinIO client when credentials are configured.

        Without credentials the client falls back to unsigned HTTP requests,
        which keeps anonymous/read-only gateways working as before.
        """
        if self._minio_initialized:
            return self._minio
        self._minio_initialized = True
        if not (self._endpoint and self._access_key and self._secret_key):
            return None
        try:
            from minio import Minio
        except ImportError:  # pragma: no cover - dependency is declared
            logger.warning("minio package missing; using unsigned HTTP S3 access")
            return None
        endpoint = self._endpoint.removeprefix("https://").removeprefix("http://")
        self._minio = Minio(
            endpoint,
            access_key=self._access_key,
            secret_key=self._secret_key,
            secure=self._endpoint.startswith("https"),
            region=self._region,
        )
        return self._minio

    @staticmethod
    async def _release(response: Any) -> None:
        """Release a MinIO response connection (see ``RawDataLake.get_raw``)."""
        for method_name in ("close", "release_conn"):
            method = getattr(response, method_name, None)
            if method is not None:
                await asyncio.to_thread(method)

    async def write(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Result[str]:
        client = self._minio_client()
        if client is not None:
            return await self._write_signed(client, key, data, content_type)
        return await self._write_http(key, data, content_type)

    async def _write_signed(
        self, client: Any, key: str, data: bytes, content_type: str
    ) -> Result[str]:
        try:
            await asyncio.to_thread(
                client.put_object,
                self._bucket,
                key,
                io.BytesIO(data),
                len(data),
                content_type=content_type,
            )
            return Result.ok(key)
        except Exception as exc:  # noqa: BLE001 - SDK/urllib3 error surface
            code = _classify_s3_error(exc)
            logger.warning("S3 write failed for %s (%s): %s", key, code, exc)
            return Result.fail(f"S3 write failed for {key}: {exc}", code=code)

    async def _write_http(self, key: str, data: bytes, content_type: str) -> Result[str]:
        client = await self._get_client()
        url = f"/{self._bucket}/{key}"
        headers = {"Content-Type": content_type, "Content-Length": str(len(data))}
        try:
            resp = await client.put(url, content=data, headers=headers)
        except httpx.TimeoutException as exc:
            return Result.fail(f"S3 write timed out for {key}: {exc}", code="timeout")
        except httpx.HTTPError as exc:
            return Result.fail(f"S3 write failed for {key}: {exc}", code="connection_error")
        code = _classify_http_status(resp.status_code)
        if code is not None:
            return Result.fail(f"S3 write failed for {key}: HTTP {resp.status_code}", code=code)
        return Result.ok(key)

    async def read(self, key: str) -> Result[bytes]:
        client = self._minio_client()
        if client is not None:
            return await self._read_signed(client, key)
        return await self._read_http(key)

    async def _read_signed(self, client: Any, key: str) -> Result[bytes]:
        response: Any | None = None
        try:
            response = await asyncio.to_thread(client.get_object, self._bucket, key)
            data = await asyncio.to_thread(response.read)
            return Result.ok(data)
        except Exception as exc:  # noqa: BLE001 - SDK/urllib3 error surface
            code = _classify_s3_error(exc)
            logger.warning("S3 read failed for %s (%s): %s", key, code, exc)
            return Result.fail(f"S3 read failed for {key}: {exc}", code=code)
        finally:
            if response is not None:
                await self._release(response)

    async def _read_http(self, key: str) -> Result[bytes]:
        client = await self._get_client()
        url = f"/{self._bucket}/{key}"
        try:
            resp = await client.get(url)
        except httpx.TimeoutException as exc:
            return Result.fail(f"S3 read timed out for {key}: {exc}", code="timeout")
        except httpx.HTTPError as exc:
            return Result.fail(f"S3 read failed for {key}: {exc}", code="connection_error")
        code = _classify_http_status(resp.status_code)
        if code is not None:
            return Result.fail(f"S3 read failed for {key}: HTTP {resp.status_code}", code=code)
        return Result.ok(resp.content)

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
        self._minio = None
