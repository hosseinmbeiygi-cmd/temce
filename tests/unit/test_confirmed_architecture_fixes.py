"""Regression tests for confirmed ingestion/integration reliability fixes."""

from __future__ import annotations

from types import SimpleNamespace

import aiohttp
import httpx
import pytest

from ingestion.config import IngestionConfig
from ingestion.identity import IdentityResolver
from ingestion.lake import RawDataLake
from ingestion.retry import retry_async
from ingestion.sources.base import SourcePayload


@pytest.mark.asyncio
async def test_retry_async_retries_transient_http_status(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("ingestion.retry.asyncio.sleep", fake_sleep)

    async def fetch() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise aiohttp.ClientResponseError(
                request_info=SimpleNamespace(real_url="https://example.test"),
                history=(),
                status=503,
                message="temporarily unavailable",
                headers={"Retry-After": "0"},
            )
        return "ok"

    assert await retry_async(fetch, max_retries=3) == "ok"
    assert calls == 3
    assert len(sleeps) == 2


@pytest.mark.asyncio
async def test_retry_async_does_not_retry_permanent_http_status(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def fake_sleep(_: float) -> None:
        raise AssertionError("permanent HTTP errors must not sleep/retry")

    monkeypatch.setattr("ingestion.retry.asyncio.sleep", fake_sleep)

    async def fetch() -> None:
        nonlocal calls
        calls += 1
        raise aiohttp.ClientResponseError(
            request_info=SimpleNamespace(real_url="https://example.test"),
            history=(),
            status=404,
            message="not found",
        )

    with pytest.raises(aiohttp.ClientResponseError):
        await retry_async(fetch, max_retries=3)
    assert calls == 1


@pytest.mark.asyncio
async def test_raw_lake_rejects_default_credentials_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.config.settings", SimpleNamespace(is_production=True))
    lake = RawDataLake(IngestionConfig())

    with pytest.raises(RuntimeError, match="non-default MinIO credentials"):
        await lake.start()


def test_source_payload_metadata_is_not_shared() -> None:
    first = SourcePayload(
        source="test",
        endpoint="/one",
        raw_data=b"1",
        content_type="application/octet-stream",
        fetch_time="2026-01-01T00:00:00Z",
    )
    second = SourcePayload(
        source="test",
        endpoint="/two",
        raw_data=b"2",
        content_type="application/octet-stream",
        fetch_time="2026-01-01T00:00:00Z",
    )

    first.metadata["request_id"] = "one"
    assert second.metadata == {}


class _IdentityDb:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, query: str, *args: object):
        normalized = query.strip()
        if normalized.startswith("SELECT i.id"):
            return None
        if normalized.startswith("SELECT instrument_id"):
            return {"instrument_id": "winner"}
        if normalized.startswith("INSERT INTO instruments"):
            return {"id": "winner"}
        return None

    async def execute(self, query: str, *args: object) -> str:
        self.executed.append((query, args))
        return "INSERT 0 1"


@pytest.mark.asyncio
async def test_integrations_http_client_does_not_retry_permanent_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    from integrations.http_client import HttpClient

    class FakeClient:
        calls = 0

        async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
            self.calls += 1
            request = httpx.Request(method, url)
            return httpx.Response(404, request=request)

    fake = FakeClient()
    client = HttpClient(base_url="https://example.test", max_retries=3)

    async def get_client() -> FakeClient:
        return fake

    monkeypatch.setattr(client, "_get_client", get_client)
    with pytest.raises(httpx.HTTPStatusError):
        await client.get("/missing")
    assert fake.calls == 1


@pytest.mark.asyncio
async def test_integrations_http_client_retries_transient_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    from integrations.http_client import HttpClient

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
            self.calls += 1
            request = httpx.Request(method, url)
            return httpx.Response(503 if self.calls == 1 else 200, request=request)

    fake = FakeClient()
    client = HttpClient(base_url="https://example.test", max_retries=3)

    async def fake_sleep(_: float) -> None:
        return None

    async def get_client() -> FakeClient:
        return fake

    monkeypatch.setattr(client, "_get_client", get_client)
    monkeypatch.setattr("integrations.http_client.asyncio.sleep", fake_sleep)
    response = await client.get("/temporary")
    assert response.status_code == 200
    assert fake.calls == 2


@pytest.mark.asyncio
async def test_identity_resolver_returns_database_winner() -> None:
    db = _IdentityDb()
    resolver = IdentityResolver(db)

    result = await resolver.resolve_or_create(
        source="tsetmc",
        external_id="external-1",
        symbol="TEST",
    )

    assert result == "winner"
    assert any("ON CONFLICT (source, external_id) DO NOTHING" in query for query, _ in db.executed)
