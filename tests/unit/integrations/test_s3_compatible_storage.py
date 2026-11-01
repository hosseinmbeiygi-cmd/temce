"""Unit tests for S3-compatible storage error classification."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from integrations.filesystems.s3_compatible_storage import (
    S3CompatibleStorage,
    _classify_s3_error,
)


def _unsigned_storage(handler: Callable[[httpx.Request], httpx.Response]) -> S3CompatibleStorage:
    """Build a storage client on top of httpx.MockTransport (no credentials)."""
    storage = S3CompatibleStorage(
        endpoint_url="http://s3.test",
        access_key="",
        secret_key="",
        bucket="bucket",
    )
    # Force the unsigned HTTP path regardless of ambient env credentials.
    storage._minio_initialized = True
    storage._minio = None
    storage._client = httpx.AsyncClient(
        base_url="http://s3.test",
        transport=httpx.MockTransport(handler),
    )
    return storage


def _responder(status: int, body: bytes = b"") -> Callable[[httpx.Request], httpx.Response]:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body)

    return _handler


class _FakeS3Error(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def test_classify_minio_error_codes() -> None:
    assert _classify_s3_error(_FakeS3Error("NoSuchKey")) == "not_found"
    assert _classify_s3_error(_FakeS3Error("NoSuchBucket")) == "not_found"
    assert _classify_s3_error(_FakeS3Error("AccessDenied")) == "forbidden"
    assert _classify_s3_error(_FakeS3Error("SignatureDoesNotMatch")) == "forbidden"
    assert _classify_s3_error(TimeoutError("timed out")) == "timeout"
    assert _classify_s3_error(RuntimeError("boom")) == "s3_error"


@pytest.mark.asyncio
async def test_read_success() -> None:
    storage = _unsigned_storage(_responder(200, b"payload"))
    result = await storage.read("codal/x.pdf")
    assert result.success is True
    assert result.value == b"payload"
    await storage.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [(404, "not_found"), (403, "forbidden"), (408, "timeout"), (500, "server_error")],
)
async def test_read_http_errors_are_classified(status: int, code: str) -> None:
    storage = _unsigned_storage(_responder(status))
    result = await storage.read("codal/x.pdf")
    assert result.success is False
    assert result.error_code == code
    await storage.close()


@pytest.mark.asyncio
async def test_read_timeout_and_connection_errors_are_classified() -> None:
    def _timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    def _connect_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    storage = _unsigned_storage(_timeout)
    timeout_result = await storage.read("codal/x.pdf")
    assert timeout_result.error_code == "timeout"
    await storage.close()

    storage = _unsigned_storage(_connect_error)
    connect_result = await storage.read("codal/x.pdf")
    assert connect_result.error_code == "connection_error"
    await storage.close()


@pytest.mark.asyncio
async def test_write_success_and_failure() -> None:
    storage = _unsigned_storage(_responder(200))
    result = await storage.write("codal/x.pdf", b"data", "application/pdf")
    assert result.success is True
    assert result.value == "codal/x.pdf"
    await storage.close()

    storage = _unsigned_storage(_responder(403))
    forbidden = await storage.write("codal/x.pdf", b"data", "application/pdf")
    assert forbidden.success is False
    assert forbidden.error_code == "forbidden"
    await storage.close()
