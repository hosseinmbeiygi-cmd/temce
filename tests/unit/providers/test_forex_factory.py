"""TDD tests for the Forex Factory XML calendar client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ── sample XML ────────────────────────────────────────────────────────────────

_SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<weeklyevents>
  <event>
    <title>Non-Farm Employment Change</title>
    <country>USD</country>
    <date>Nov 08, 2026</date>
    <time>8:30am</time>
    <impact>High</impact>
    <forecast>185K</forecast>
    <previous>223K</previous>
    <actual>190K</actual>
  </event>
  <event>
    <title>CPI m/m</title>
    <country>USD</country>
    <date>Nov 12, 2026</date>
    <time>8:30am</time>
    <impact>High</impact>
    <forecast>0.2%</forecast>
    <previous>0.2%</previous>
    <actual></actual>
  </event>
  <event>
    <title>German Manufacturing PMI</title>
    <country>EUR</country>
    <date>Nov 11, 2026</date>
    <time>3:30am</time>
    <impact>Medium</impact>
    <forecast>45.1</forecast>
    <previous>44.5</previous>
    <actual></actual>
  </event>
  <event>
    <title>Low impact event</title>
    <country>USD</country>
    <date>Nov 10, 2026</date>
    <time>All Day</time>
    <impact>Low</impact>
    <forecast></forecast>
    <previous></previous>
    <actual></actual>
  </event>
</weeklyevents>"""


def _mock_client(xml_text: str = _SAMPLE_XML) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.text = xml_text
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    client.aclose = AsyncMock()
    return client


# ── 1. Import ─────────────────────────────────────────────────────────────────

def test_importable():
    from providers.macro_sources.forex_factory import (  # noqa: F401
        FF_CALENDAR_URL,
        ForexFactoryCalendarClient,
        ForexFactoryEvent,
        ForexFactoryProvider,
        fetch_ff_calendar,
    )


# ── 2. XML parsing — full feed ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_high_impact_events_by_default():
    from providers.macro_sources.forex_factory import ForexFactoryCalendarClient

    events = await ForexFactoryCalendarClient(client=_mock_client()).fetch()
    # Default min_impact="High" → NFP and CPI only (not Medium or Low)
    assert len(events) == 2
    titles = {e.title for e in events}
    assert "Non-Farm Employment Change" in titles
    assert "CPI m/m" in titles


@pytest.mark.asyncio
async def test_fetch_medium_impact_includes_medium_and_high():
    from providers.macro_sources.forex_factory import ForexFactoryCalendarClient

    events = await ForexFactoryCalendarClient(client=_mock_client()).fetch(min_impact="Medium")
    assert len(events) == 3  # NFP + CPI + German PMI


@pytest.mark.asyncio
async def test_fetch_no_filter_returns_all():
    from providers.macro_sources.forex_factory import ForexFactoryCalendarClient

    events = await ForexFactoryCalendarClient(client=_mock_client()).fetch(min_impact=None)
    assert len(events) == 4


@pytest.mark.asyncio
async def test_fetch_country_filter():
    from providers.macro_sources.forex_factory import ForexFactoryCalendarClient

    events = await ForexFactoryCalendarClient(client=_mock_client()).fetch(
        min_impact="Medium", country="EUR"
    )
    assert len(events) == 1
    assert events[0].title == "German Manufacturing PMI"


# ── 3. Event field mapping ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_fields_populated():
    from providers.macro_sources.forex_factory import ForexFactoryCalendarClient

    events = await ForexFactoryCalendarClient(client=_mock_client()).fetch()
    nfp = next(e for e in events if "Non-Farm" in e.title)

    assert nfp.country == "USD"
    assert "2026" in nfp.date
    assert nfp.impact == "High"
    assert nfp.forecast == "185K"
    assert nfp.previous == "223K"
    assert nfp.actual == "190K"


@pytest.mark.asyncio
async def test_empty_actual_becomes_none():
    from providers.macro_sources.forex_factory import ForexFactoryCalendarClient

    events = await ForexFactoryCalendarClient(client=_mock_client()).fetch()
    cpi = next(e for e in events if "CPI" in e.title)
    assert cpi.actual is None


# ── 4. Error handling ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_empty_on_network_error():
    from providers.macro_sources.forex_factory import ForexFactoryCalendarClient

    bad = MagicMock()
    bad.get = AsyncMock(side_effect=Exception("timeout"))
    bad.aclose = AsyncMock()

    events = await ForexFactoryCalendarClient(client=bad).fetch()
    assert events == []


@pytest.mark.asyncio
async def test_fetch_returns_empty_on_bad_xml():
    from providers.macro_sources.forex_factory import ForexFactoryCalendarClient

    events = await ForexFactoryCalendarClient(client=_mock_client("not xml at all")).fetch()
    assert events == []


# ── 5. ForexFactoryProvider (BaseProvider wrapper) ───────────────────────────

@pytest.mark.asyncio
async def test_provider_fetch_returns_result_ok():
    from providers.macro_sources.forex_factory import ForexFactoryProvider

    provider = ForexFactoryProvider(client=_mock_client())
    result = await provider.fetch()

    assert result.success
    assert isinstance(result.value, list)
    assert len(result.value) == 2  # default High only


@pytest.mark.asyncio
async def test_provider_fetch_returns_fail_when_no_events():
    from providers.macro_sources.forex_factory import ForexFactoryProvider

    # XML with only Low impact events
    low_xml = """<weeklyevents>
      <event>
        <title>Low event</title><country>USD</country><date>Nov 10, 2026</date>
        <time>All Day</time><impact>Low</impact>
        <forecast></forecast><previous></previous><actual></actual>
      </event>
    </weeklyevents>"""
    provider = ForexFactoryProvider(client=_mock_client(low_xml))
    result = await provider.fetch()
    assert not result.success


@pytest.mark.asyncio
async def test_provider_health_healthy():
    from providers.macro_sources.forex_factory import ForexFactoryProvider

    provider = ForexFactoryProvider(client=_mock_client())
    h = await provider.health()
    assert h["healthy"] is True


# ── 6. Convenience function ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_ff_calendar_convenience():
    from providers.macro_sources.forex_factory import fetch_ff_calendar

    events = await fetch_ff_calendar(client=_mock_client(), min_impact="High")
    assert len(events) == 2
