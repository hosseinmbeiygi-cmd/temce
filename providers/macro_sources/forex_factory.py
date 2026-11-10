"""Forex Factory economic calendar — weekly XML feed.

Endpoint: ``http://nfs.faireconomy.media/ff_calendar_thisweek.xml``
No API key required. Returns the current week's high-impact events.

Useful for: NFP, CPI, Fed rate decisions, and other macro releases that
directly drive gold price movements.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider

logger = get_logger(__name__)

FF_CALENDAR_URL = "http://nfs.faireconomy.media/ff_calendar_thisweek.xml"
DEFAULT_TIMEOUT_SECONDS: float = 10.0

# Impact labels in the FF XML
_HIGH_IMPACT = {"High"}
_MEDIUM_IMPACT = {"Medium", "High"}


@dataclass(frozen=True)
class ForexFactoryEvent:
    """One economic calendar event from Forex Factory."""

    title: str
    country: str
    date: str            # ISO format e.g. "2026-11-10"
    time: str            # e.g. "8:30am" or "All Day"
    impact: str          # "Low" | "Medium" | "High" | "Holiday"
    forecast: str | None
    previous: str | None
    actual: str | None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ForexFactoryCalendarClient:
    """Fetch and parse the Forex Factory weekly economic calendar.

    Inject ``client`` in tests to avoid real network calls.
    """

    def __init__(
        self,
        *,
        url: str = FF_CALENDAR_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._url = url
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def fetch(
        self,
        *,
        min_impact: str | None = "High",
        country: str | None = None,
    ) -> list[ForexFactoryEvent]:
        """Return this week's calendar events, filtered by impact/country.

        Args:
            min_impact: minimum impact level — ``"High"``, ``"Medium"`` or ``None`` (all).
            country: 2-letter ISO country code (``"US"``, ``"EU"`` etc.) or None for all.
        """
        close_client = self._client is None
        http = self._client or httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
        )
        try:
            resp = await http.get(self._url)
            resp.raise_for_status()
            xml_text = resp.text
        except Exception as exc:
            logger.warning("ForexFactory fetch failed: %s", exc)
            return []
        finally:
            if close_client:
                await http.aclose()

        return _parse_ff_xml(xml_text, min_impact=min_impact, country=country)


def _parse_ff_xml(
    xml_text: str,
    *,
    min_impact: str | None,
    country: str | None,
) -> list[ForexFactoryEvent]:
    """Parse Forex Factory XML into a list of events."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("ForexFactory XML parse error: %s", exc)
        return []

    impact_filter: set[str] | None = None
    if min_impact == "High":
        impact_filter = _HIGH_IMPACT
    elif min_impact == "Medium":
        impact_filter = _MEDIUM_IMPACT

    events: list[ForexFactoryEvent] = []
    for ev in root.findall("event"):
        title   = (ev.findtext("title")    or "").strip()
        ctry    = (ev.findtext("country")  or "").strip()
        date    = (ev.findtext("date")     or "").strip()
        time    = (ev.findtext("time")     or "").strip()
        impact  = (ev.findtext("impact")   or "").strip()
        forecast = ev.findtext("forecast")
        previous = ev.findtext("previous")
        actual   = ev.findtext("actual")

        if impact_filter and impact not in impact_filter:
            continue
        if country and ctry.upper() != country.upper():
            continue

        events.append(ForexFactoryEvent(
            title=title,
            country=ctry,
            date=date,
            time=time,
            impact=impact,
            forecast=forecast or None,
            previous=previous or None,
            actual=actual or None,
        ))
    return events


class ForexFactoryProvider(BaseProvider):
    """Macro provider wrapping the Forex Factory weekly XML calendar.

    Args:
        client: injectable httpx.AsyncClient for testing.
        min_impact: minimum event impact to return (``"High"`` default).
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        min_impact: str = "High",
    ) -> None:
        super().__init__(name="forex_factory_calendar")
        self._ff = ForexFactoryCalendarClient(client=client)
        self._min_impact = min_impact

    async def fetch(
        self,
        country: str | None = None,
        min_impact: str | None = None,
        **kwargs: Any,
    ) -> Result[Any]:
        """Return this week's economic events.

        Args:
            country: filter by country (e.g. ``"US"``).
            min_impact: override the default impact filter.
        """
        events = await self._ff.fetch(
            min_impact=min_impact or self._min_impact,
            country=country,
        )
        if not events:
            return Result.fail("ForexFactory returned no events")

        data = [
            {
                "title":    e.title,
                "country":  e.country,
                "date":     e.date,
                "time":     e.time,
                "impact":   e.impact,
                "forecast": e.forecast,
                "previous": e.previous,
                "actual":   e.actual,
            }
            for e in events
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        events = await self._ff.fetch(min_impact=None)
        if events:
            return {"healthy": True, "message": f"{len(events)} events this week"}
        return {"healthy": False, "message": "ForexFactory calendar unavailable"}


async def fetch_ff_calendar(
    *,
    min_impact: str | None = "High",
    country: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[ForexFactoryEvent]:
    """Convenience function — fetch Forex Factory calendar without an instance."""
    return await ForexFactoryCalendarClient(client=client).fetch(
        min_impact=min_impact,
        country=country,
    )
