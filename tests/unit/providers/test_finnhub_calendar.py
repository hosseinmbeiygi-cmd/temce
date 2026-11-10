"""TDD tests for the Finnhub economic calendar client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


_SAMPLE_PAYLOAD = {
    "economicCalendar": [
        {
            "event":    "CPI YoY",
            "country":  "US",
            "time":     "2026-11-12T13:30:00+00:00",
            "impact":   "high",
            "actual":   3.2,
            "estimate": 3.1,
            "prev":     3.4,
            "unit":     "%",
        },
        {
            "event":    "German GDP QoQ",
            "country":  "DE",
            "time":     "2026-11-14T07:00:00+00:00",
            "impact":   "medium",
            "actual":   None,
            "estimate": -0.1,
            "prev":     -0.3,
            "unit":     "%",
        },
    ]
}


def _mock_client(payload: dict = _SAMPLE_PAYLOAD) -> MagicMock:
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
        FinnhubEvent,
        FinnhubProvider,
    )


# ── 2. fetch_calendar — happy path ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_calendar_returns_events():
    from providers.macro_sources.finnhub import FinnhubClient

    client = FinnhubClient(api_key="test-key", client=_mock_client())
    events = await client.fetch_calendar()
    assert len(events) == 2


@pytest.mark.asyncio
async def test_event_fields_populated():
    from providers.macro_sources.finnhub import FinnhubClient

    client = FinnhubClient(api_key="test-key", client=_mock_client())
    events = await client.fetch_calendar()
    cpi = events[0]

    assert cpi.event == "CPI YoY"
    assert cpi.country == "US"
    assert cpi.impact == "high"
    assert cpi.actual == pytest.approx(3.2)
    assert cpi.estimate == pytest.approx(3.1)
    assert cpi.prev == pytest.approx(3.4)
    assert cpi.unit == "%"


@pytest.mark.asyncio
async def test_none_actual_stays_none():
    from providers.macro_sources.finnhub import FinnhubClient

    client = FinnhubClient(api_key="test-key", client=_mock_client())
    events = await client.fetch_calendar()
    gdp = events[1]
    assert gdp.actual is None


# ── 3. Error handling ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_api_key_raises():
    from providers.macro_sources.finnhub import FinnhubClient
    from providers.macro_sources.base import MacroSourceError

    client = FinnhubClient(api_key="", client=_mock_client())
    with pytest.raises(MacroSourceError, match="FINNHUB_API_KEY"):
        await client.fetch_calendar()


@pytest.mark.asyncio
async def test_network_error_returns_empty():
    from providers.macro_sources.finnhub import FinnhubClient

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("connection refused"))
    bad.aclose = AsyncMock()

    client = FinnhubClient(api_key="test-key", client=bad)
    events = await client.fetch_calendar()
    assert events == []


# ── 4. FinnhubProvider ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_fetch_returns_result_ok():
    from providers.macro_sources.finnhub import FinnhubProvider

    import providers.macro_sources.finnhub as module
    orig = module._get_finnhub_key
    module._get_finnhub_key = lambda: "test-key"
    try:
        provider = FinnhubProvider(client=_mock_client())
        result = await provider.fetch()
    finally:
        module._get_finnhub_key = orig

    assert result.success
    assert len(result.value) == 2


@pytest.mark.asyncio
async def test_provider_fetch_country_filter():
    from providers.macro_sources.finnhub import FinnhubProvider

    import providers.macro_sources.finnhub as module
    orig = module._get_finnhub_key
    module._get_finnhub_key = lambda: "test-key"
    try:
        provider = FinnhubProvider(client=_mock_client())
        result = await provider.fetch(country="US")
    finally:
        module._get_finnhub_key = orig

    assert result.success
    assert len(result.value) == 1
    assert result.value[0]["country"] == "US"


@pytest.mark.asyncio
async def test_provider_returns_fail_on_missing_key():
    from providers.macro_sources.finnhub import FinnhubProvider

    import providers.macro_sources.finnhub as module
    orig = module._get_finnhub_key
    module._get_finnhub_key = lambda: ""
    try:
        provider = FinnhubProvider(client=_mock_client())
        result = await provider.fetch()
    finally:
        module._get_finnhub_key = orig

    assert not result.success
    assert "FINNHUB_API_KEY" in result.error
