"""Unit tests for the gold spot providers.

All HTTP is served by ``httpx.MockTransport``; no real network calls.
"""

from __future__ import annotations

import httpx
import pytest

from providers.gold_spot import (
    BrsApiGoldSpotProvider,
    GoldSpotProviderError,
    YahooGoldSpotProvider,
    build_default_gold_spot_providers,
)

NOW = 1_700_000_000


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _brsapi_payload(price: float = 2_400.0, time_unix: int = NOW) -> dict:
    return {
        "gold": {
            "ounce": [
                {"symbol": "XAUUSD", "price": price, "time_unix": time_unix},
            ]
        }
    }


def test_brsapi_returns_ounce_price_and_timestamp() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/Market/Gold_Currency_Pro.php"
        assert request.url.params["section"] == "gold"
        assert request.url.params["key"] == "test-key"
        return httpx.Response(200, json=_brsapi_payload())

    provider = BrsApiGoldSpotProvider(
        api_key="test-key", enabled=True, client=_mock_client(handler)
    )

    assert provider.fetch() == {"price": 2_400.0, "timestamp": float(NOW)}


def test_brsapi_http_500_raises() -> None:
    provider = BrsApiGoldSpotProvider(
        api_key="test-key",
        enabled=True,
        client=_mock_client(lambda request: httpx.Response(500, text="boom")),
    )

    with pytest.raises(httpx.HTTPStatusError):
        provider.fetch()


def test_brsapi_missing_key_raises() -> None:
    provider = BrsApiGoldSpotProvider(
        api_key="",
        enabled=True,
        client=_mock_client(lambda request: httpx.Response(200, json=_brsapi_payload())),
    )

    with pytest.raises(GoldSpotProviderError, match="API key"):
        provider.fetch()


def test_brsapi_missing_xauusd_raises() -> None:
    payload = {"gold": {"ounce": [{"symbol": "XAGUSD", "price": 30.0, "time_unix": NOW}]}}
    provider = BrsApiGoldSpotProvider(
        api_key="test-key",
        enabled=True,
        client=_mock_client(lambda request: httpx.Response(200, json=payload)),
    )

    with pytest.raises(GoldSpotProviderError, match="XAUUSD"):
        provider.fetch()


def test_brsapi_missing_timestamp_raises() -> None:
    payload = {"gold": {"ounce": [{"symbol": "XAUUSD", "price": 2_400.0}]}}
    provider = BrsApiGoldSpotProvider(
        api_key="test-key",
        enabled=True,
        client=_mock_client(lambda request: httpx.Response(200, json=payload)),
    )

    with pytest.raises(GoldSpotProviderError, match="timestamp"):
        provider.fetch()


def test_yahoo_returns_meta_price_and_timestamp() -> None:
    payload = {
        "chart": {
            "result": [
                {"meta": {"regularMarketPrice": 2_401.5, "regularMarketTime": NOW}},
            ],
            "error": None,
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v8/finance/chart/GC=F"
        return httpx.Response(200, json=payload)

    provider = YahooGoldSpotProvider(client=_mock_client(handler))

    assert provider.fetch() == {"price": 2_401.5, "timestamp": float(NOW)}


def test_yahoo_http_500_raises() -> None:
    provider = YahooGoldSpotProvider(
        client=_mock_client(lambda request: httpx.Response(500, text="boom")),
    )

    with pytest.raises(httpx.HTTPStatusError):
        provider.fetch()


def test_yahoo_malformed_payload_raises() -> None:
    provider = YahooGoldSpotProvider(
        client=_mock_client(lambda request: httpx.Response(200, json={"chart": {}})),
    )

    with pytest.raises(GoldSpotProviderError, match="Yahoo"):
        provider.fetch()


def test_default_providers_are_primary_then_backup() -> None:
    providers = build_default_gold_spot_providers()

    assert [provider.name for provider in providers] == ["brsapi", "yahoo"]
