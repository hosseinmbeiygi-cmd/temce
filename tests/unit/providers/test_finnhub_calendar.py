"""TDD tests for Finnhub providers (news + earnings).

Endpoints covered (all FREE tier):
  GET /news                 → FinnhubNewsProvider
  GET /calendar/earnings    → FinnhubEarningsProvider
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ── Sample payloads ───────────────────────────────────────────────────────────

_SAMPLE_NEWS = [
    {
        "category": "general",
        "datetime": 1731240600,
        "headline": "Gold rises as dollar weakens",
        "id": 12345,
        "image": "https://example.com/img.jpg",
        "related": "XAUUSD",
        "source": "Reuters",
        "summary": "Gold climbed 0.8% on Tuesday as the dollar weakened.",
        "url": "https://reuters.com/gold-rises",
    },
    {
        "category": "forex",
        "datetime": 1731200000,
        "headline": "Fed signals pause on rate hikes",
        "id": 12346,
        "image": "",
        "related": "",
        "source": "CNBC",
        "summary": "The Federal Reserve signalled a pause.",
        "url": "https://cnbc.com/fed-pause",
    },
]

_SAMPLE_EARNINGS = {
    "earningsCalendar": [
        {
            "symbol": "AAPL",
            "date": "2026-11-15",
            "hour": "amc",
            "epsEstimate": 1.43,
            "epsActual": None,
            "revenueEstimate": 94_000_000_000,
            "revenueActual": None,
            "quarter": 4,
            "year": 2026,
        },
        {
            "symbol": "MSFT",
            "date": "2026-11-20",
            "hour": "bmo",
            "epsEstimate": 2.80,
            "epsActual": 2.95,
            "revenueEstimate": 65_000_000_000,
            "revenueActual": 66_200_000_000,
            "quarter": 1,
            "year": 2027,
        },
    ]
}


def _mock_client(payload) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


# ── 1. Import ─────────────────────────────────────────────────────────────────

def test_importable():
    from providers.macro_sources.finnhub import (  # noqa: F401
        FINNHUB_BASE_URL,
        FinnhubClient,
        FinnhubNewsItem,
        FinnhubNewsProvider,
        FinnhubEarningsProvider,
        FinnhubEarning,
        FinnhubProvider,          # backward-compat alias
        NEWS_CATEGORIES,
    )


def test_finnhub_provider_is_alias_for_news_provider():
    from providers.macro_sources.finnhub import FinnhubProvider, FinnhubNewsProvider
    assert FinnhubProvider is FinnhubNewsProvider


# ── 2. fetch_news — happy path ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_news_returns_items():
    from providers.macro_sources.finnhub import FinnhubClient

    client = FinnhubClient(api_key="test-key", client=_mock_client(_SAMPLE_NEWS))
    items = await client.fetch_news(category="general")
    assert len(items) == 2


@pytest.mark.asyncio
async def test_fetch_news_fields_populated():
    from providers.macro_sources.finnhub import FinnhubClient

    client = FinnhubClient(api_key="test-key", client=_mock_client(_SAMPLE_NEWS))
    items = await client.fetch_news()
    first = items[0]

    assert first.headline == "Gold rises as dollar weakens"
    assert first.source == "Reuters"
    assert first.id == 12345
    assert first.related == "XAUUSD"
    assert first.datetime_ts == 1731240600


@pytest.mark.asyncio
async def test_fetch_news_datetime_converted_to_iso():
    from providers.macro_sources.finnhub import FinnhubClient

    client = FinnhubClient(api_key="test-key", client=_mock_client(_SAMPLE_NEWS))
    items = await client.fetch_news()
    # UNIX 1731240600 → 2024-11-10T12:10:00+00:00
    assert items[0].datetime_ts == 1731240600
    assert "T" in items[0].published_at   # ISO-8601 format confirmed


@pytest.mark.asyncio
async def test_fetch_news_invalid_category_raises():
    from providers.macro_sources.finnhub import FinnhubClient
    from providers.macro_sources.base import MacroSourceError

    client = FinnhubClient(api_key="test-key", client=_mock_client(_SAMPLE_NEWS))
    with pytest.raises(MacroSourceError, match="Invalid category"):
        await client.fetch_news(category="gold")


# ── 3. fetch_news — error paths ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_api_key_raises():
    from providers.macro_sources.finnhub import FinnhubClient
    from providers.macro_sources.base import MacroSourceError

    client = FinnhubClient(api_key="", client=_mock_client(_SAMPLE_NEWS))
    with pytest.raises(MacroSourceError, match="FINNHUB_API_KEY"):
        await client.fetch_news()


@pytest.mark.asyncio
async def test_network_error_returns_empty():
    from providers.macro_sources.finnhub import FinnhubClient

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("connection refused"))
    bad.aclose = AsyncMock()

    client = FinnhubClient(api_key="test-key", client=bad)
    items = await client.fetch_news()
    assert items == []


# ── 4. FinnhubNewsProvider ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_news_provider_fetch_returns_result_ok():
    from providers.macro_sources.finnhub import FinnhubNewsProvider

    import providers.macro_sources.finnhub as mod
    orig = mod._get_finnhub_key
    mod._get_finnhub_key = lambda: "test-key"
    try:
        provider = FinnhubNewsProvider(client=_mock_client(_SAMPLE_NEWS))
        result = await provider.fetch(category="general")
    finally:
        mod._get_finnhub_key = orig

    assert result.success
    assert len(result.value) == 2
    assert result.value[0]["headline"] == "Gold rises as dollar weakens"


@pytest.mark.asyncio
async def test_news_provider_respects_limit():
    from providers.macro_sources.finnhub import FinnhubNewsProvider

    import providers.macro_sources.finnhub as mod
    orig = mod._get_finnhub_key
    mod._get_finnhub_key = lambda: "test-key"
    try:
        provider = FinnhubNewsProvider(client=_mock_client(_SAMPLE_NEWS))
        result = await provider.fetch(limit=1)
    finally:
        mod._get_finnhub_key = orig

    assert len(result.value) == 1


@pytest.mark.asyncio
async def test_news_provider_returns_fail_on_missing_key():
    from providers.macro_sources.finnhub import FinnhubNewsProvider

    import providers.macro_sources.finnhub as mod
    orig = mod._get_finnhub_key
    mod._get_finnhub_key = lambda: ""
    try:
        provider = FinnhubNewsProvider(client=_mock_client(_SAMPLE_NEWS))
        result = await provider.fetch()
    finally:
        mod._get_finnhub_key = orig

    assert not result.success
    assert "FINNHUB_API_KEY" in result.error


# ── 5. fetch_earnings_calendar ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_earnings_returns_items():
    from providers.macro_sources.finnhub import FinnhubClient

    client = FinnhubClient(api_key="test-key", client=_mock_client(_SAMPLE_EARNINGS))
    items = await client.fetch_earnings_calendar()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_earnings_fields_populated():
    from providers.macro_sources.finnhub import FinnhubClient

    client = FinnhubClient(api_key="test-key", client=_mock_client(_SAMPLE_EARNINGS))
    items = await client.fetch_earnings_calendar()
    aapl = items[0]

    assert aapl.symbol == "AAPL"
    assert aapl.date == "2026-11-15"
    assert aapl.hour == "amc"
    assert aapl.eps_estimate == pytest.approx(1.43)
    assert aapl.eps_actual is None
    assert aapl.quarter == 4
    assert aapl.year == 2026


@pytest.mark.asyncio
async def test_earnings_actual_values_populated():
    from providers.macro_sources.finnhub import FinnhubClient

    client = FinnhubClient(api_key="test-key", client=_mock_client(_SAMPLE_EARNINGS))
    items = await client.fetch_earnings_calendar()
    msft = items[1]

    assert msft.eps_actual == pytest.approx(2.95)
    assert msft.revenue_actual == pytest.approx(66_200_000_000)


# ── 6. FinnhubEarningsProvider ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_earnings_provider_fetch_returns_result_ok():
    from providers.macro_sources.finnhub import FinnhubEarningsProvider

    import providers.macro_sources.finnhub as mod
    orig = mod._get_finnhub_key
    mod._get_finnhub_key = lambda: "test-key"
    try:
        provider = FinnhubEarningsProvider(client=_mock_client(_SAMPLE_EARNINGS))
        result = await provider.fetch()
    finally:
        mod._get_finnhub_key = orig

    assert result.success
    assert len(result.value) == 2
    assert result.value[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_earnings_provider_returns_fail_on_missing_key():
    from providers.macro_sources.finnhub import FinnhubEarningsProvider

    import providers.macro_sources.finnhub as mod
    orig = mod._get_finnhub_key
    mod._get_finnhub_key = lambda: ""
    try:
        provider = FinnhubEarningsProvider(client=_mock_client(_SAMPLE_EARNINGS))
        result = await provider.fetch()
    finally:
        mod._get_finnhub_key = orig

    assert not result.success
    assert "FINNHUB_API_KEY" in result.error
