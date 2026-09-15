"""Tests for the ingestion BrsApi client facade (no live HTTP)."""

from __future__ import annotations

from brsapi.client import BrsApiResponse
from core.result import Result

from ingestion.brs_api_client import (
    BROWSER_HEADERS,
    BrsApiIngestionClient,
)
from ingestion.quotas import INGESTION_QUOTA_PROFILE


class FakeLimiter:
    def __init__(self) -> None:
        self.configured: dict[str, int] = {}

    def configure(self, key: str, requests_per_minute: int) -> None:
        self.configured[key] = requests_per_minute


class FakeGovernor:
    def __init__(self, *, used: int = 10, blocked: bool = False) -> None:
        self._used = used
        self._blocked = blocked

    async def stats(self) -> dict:
        return {
            "governor": {"backend": "redis"},
            "global": {
                "daily_count": self._used,
                "daily_limit": 10_000,
                "5min_count": 3,
                "5min_limit": 300,
            },
            "block": {"blocked": self._blocked, "blocked_until": None},
        }


def _client(**kwargs) -> BrsApiIngestionClient:
    return BrsApiIngestionClient(
        limiter=kwargs.pop("limiter", FakeLimiter()),
        governor=kwargs.pop("governor", FakeGovernor()),
        **kwargs,
    )


def _response(data, status_code: int = 200) -> BrsApiResponse:
    return BrsApiResponse(
        endpoint="/Tsetmc/AllSymbols.php",
        status_code=status_code,
        data=data,
        elapsed_ms=8.5,
    )


def test_browser_headers_are_installed() -> None:
    assert "Accept-Language" in BROWSER_HEADERS
    assert BROWSER_HEADERS["Referer"].startswith("https://")
    assert "Accept" in BROWSER_HEADERS


def test_client_uses_ingestion_profile() -> None:
    client = _client()
    assert client.profile is INGESTION_QUOTA_PROFILE
    assert client.profile.daily_limit == 10_000
    assert client.profile.five_min_limit == 300


async def test_fetch_all_symbols_parses_rows(monkeypatch) -> None:
    client = _client()

    async def fake_fetch(endpoint, params=None, category_override=None):
        assert endpoint.path == "/Tsetmc/AllSymbols.php"
        assert params == {"type": "1"}
        return Result.ok(_response([{"id": "1", "l18": "فولاد", "pl": 5000}]))

    monkeypatch.setattr(client, "fetch", fake_fetch)
    result = await client.fetch_all_symbols()

    assert result.success is True
    assert result.value[0]["symbol"] == "فولاد"
    assert result.value[0]["price_last"] == 5000.0


async def test_fetch_all_symbols_fails_on_non_list_payload(monkeypatch) -> None:
    client = _client()

    async def fake_fetch(endpoint, params=None, category_override=None):
        return Result.ok(_response({"_raw_text": "<html>error</html>"}))

    monkeypatch.setattr(client, "fetch", fake_fetch)
    result = await client.fetch_all_symbols()

    assert result.success is False
    assert "AllSymbols payload unusable" in (result.error or "")


async def test_fetch_all_symbols_propagates_transport_failure(monkeypatch) -> None:
    client = _client()

    async def fake_fetch(endpoint, params=None, category_override=None):
        return Result.fail("budget exhausted")

    monkeypatch.setattr(client, "fetch", fake_fetch)
    result = await client.fetch_all_symbols()

    assert result.success is False
    assert result.error == "budget exhausted"


async def test_health_reports_quota_and_profile() -> None:
    client = _client()
    health = await client.health()

    assert health["healthy"] is True
    assert health["client_ready"] is False
    assert health["quota"]["daily_used"] == 10
    assert health["quota"]["five_min_remaining"] == 297
    assert "recommended_env" in health["profile_assessment"]


async def test_health_flags_blocked_key() -> None:
    client = _client(governor=FakeGovernor(blocked=True))
    health = await client.health()
    assert health["healthy"] is False


async def test_start_installs_browser_headers() -> None:
    limiter = FakeLimiter()
    client = _client(limiter=limiter)
    await client.start()
    try:
        headers = client._client.headers
        assert headers["Accept-Language"].startswith("fa-IR")
        assert headers["Referer"] == "https://brsapi.ir/"
        assert "Mozilla/5.0" in headers["User-Agent"]
        assert limiter.configured  # per-category buckets were seeded
    finally:
        await client.stop()
