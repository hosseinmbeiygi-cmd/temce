"""Unit tests for the BrsApiClient 502/504 retry behaviour.

Regression test: the Codal backfill aborted with "HTTP 502: bad gateway"
because ``_do_fetch`` only retried 429/503. This test locks in that 502
and 504 are now retried with backoff instead of failing immediately.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from brsapi.client import BrsApiClient


class _FakeResp:
    def __init__(self, status_code: int, content: bytes = b"{}"):
        self.status_code = status_code
        self.content = content
        self.text = "fake"
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeEndpoints:
    """Minimal stand-in for EndpointConfig objects used in fetch()."""

    class FakeEndpoint:
        path = "/Test/Endpoint.php"
        category = type("Cat", (), {"value": "tsetmc"})()
        default_params = {}

    @classmethod
    def endpoint(cls) -> FakeEndpoint:
        return cls.FakeEndpoint()


def _make_client() -> BrsApiClient:
    """Build a client with a started (mocked) httpx session."""
    client = BrsApiClient(api_key="test", base_url="http://test.local")
    client._client = AsyncMock()
    client._max_retries = 3
    return client


@pytest.mark.asyncio
async def test_502_is_retried_then_succeeds() -> None:
    client = _make_client()
    responses = [
        _FakeResp(502),  # bad gateway → retry
        _FakeResp(502),  # bad gateway → retry
        _FakeResp(200, b'{"ok": true}'),
    ]
    client._client.get = AsyncMock(side_effect=responses)
    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.fetch(_FakeEndpoints.endpoint())
    assert result.success is True
    assert client._client.get.await_count == 3  # two retries + final success


@pytest.mark.asyncio
async def test_502_exhausted_retries_fails() -> None:
    client = _make_client()
    responses = [_FakeResp(502)] * 4  # 1 attempt + 3 retries, all 502
    client._client.get = AsyncMock(side_effect=responses)
    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.fetch(_FakeEndpoints.endpoint())
    assert result.success is False
    assert "502" in (result.error or "")


@pytest.mark.asyncio
async def test_504_is_retried() -> None:
    client = _make_client()
    responses = [
        _FakeResp(504),  # gateway timeout → retry
        _FakeResp(200, b'{"ok": true}'),
    ]
    client._client.get = AsyncMock(side_effect=responses)
    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.fetch(_FakeEndpoints.endpoint())
    assert result.success is True
    assert client._client.get.await_count == 2


@pytest.mark.asyncio
async def test_401_is_not_retried() -> None:
    """Non-retryable errors should fail fast (no extra attempts)."""
    client = _make_client()
    responses = [_FakeResp(401)]
    client._client.get = AsyncMock(side_effect=responses)
    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.fetch(_FakeEndpoints.endpoint())
    assert result.success is False
    assert client._client.get.await_count == 1
