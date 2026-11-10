"""Finnhub economic calendar provider.

API: ``https://finnhub.io/api/v1/calendar/economic``
Requires ``FINNHUB_API_KEY`` environment variable.
Free tier: 60 requests/minute.

Returns macro events with forecast, previous, and actual values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.macro_sources.base import MacroSourceError

logger = get_logger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
DEFAULT_TIMEOUT_SECONDS: float = 10.0


def _get_finnhub_key() -> str:
    return os.getenv("FINNHUB_API_KEY", "")


@dataclass(frozen=True)
class FinnhubEvent:
    """One economic calendar event from Finnhub."""

    event: str
    country: str
    time: str              # ISO-8601 datetime string
    impact: str            # "high" | "medium" | "low" | ""
    actual: float | None
    estimate: float | None
    prev: float | None
    unit: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FinnhubClient:
    """Fetch Finnhub economic calendar events.

    Inject ``client`` in tests to avoid real network calls.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = FINNHUB_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or _get_finnhub_key()
        self._base_url = base_url
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def fetch_calendar(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[FinnhubEvent]:
        """Fetch economic calendar events in the given date range.

        Args:
            from_date: ``YYYY-MM-DD`` start (default: today).
            to_date: ``YYYY-MM-DD`` end (default: 7 days from today).
        """
        if not self._api_key:
            raise MacroSourceError("FINNHUB_API_KEY is not configured")

        today = date.today()
        from_str = from_date or today.isoformat()
        to_str   = to_date   or (today + timedelta(days=7)).isoformat()

        close_client = self._client is None
        http = self._client or httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
        )
        try:
            resp = await http.get(
                f"{self._base_url.rstrip('/')}/calendar/economic",
                params={"token": self._api_key, "from": from_str, "to": to_str},
            )
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPStatusError as exc:
            raise MacroSourceError(f"Finnhub HTTP {exc.response.status_code}") from exc
        except Exception as exc:
            logger.warning("Finnhub fetch failed: %s", exc)
            return []
        finally:
            if close_client:
                await http.aclose()

        raw_events: list[dict[str, Any]] = payload.get("economicCalendar") or []
        events: list[FinnhubEvent] = []
        for ev in raw_events:
            events.append(FinnhubEvent(
                event    = ev.get("event", ""),
                country  = ev.get("country", ""),
                time     = ev.get("time", ""),
                impact   = ev.get("impact", ""),
                actual   = _to_float(ev.get("actual")),
                estimate = _to_float(ev.get("estimate")),
                prev     = _to_float(ev.get("prev")),
                unit     = ev.get("unit", ""),
            ))
        return events


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


class FinnhubProvider(BaseProvider):
    """Macro provider wrapping the Finnhub economic calendar API.

    Args:
        client: injectable httpx.AsyncClient for testing.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(name="finnhub_calendar")
        self._finnhub = FinnhubClient(client=client)

    async def fetch(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        country: str | None = None,
        **kwargs: Any,
    ) -> Result[Any]:
        """Return economic calendar events.

        Args:
            from_date: ``YYYY-MM-DD`` start.
            to_date: ``YYYY-MM-DD`` end.
            country: filter by 2-letter country code (e.g. ``"US"``).
        """
        try:
            events = await self._finnhub.fetch_calendar(
                from_date=from_date,
                to_date=to_date,
            )
        except MacroSourceError as exc:
            return Result.fail(str(exc))

        if country:
            events = [e for e in events if e.country.upper() == country.upper()]

        if not events:
            return Result.fail("Finnhub returned no events for the given range")

        data = [
            {
                "event":    e.event,
                "country":  e.country,
                "time":     e.time,
                "impact":   e.impact,
                "actual":   e.actual,
                "estimate": e.estimate,
                "prev":     e.prev,
                "unit":     e.unit,
            }
            for e in events
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        try:
            events = await self._finnhub.fetch_calendar()
            if events is not None:
                return {"healthy": True, "message": f"{len(events)} events returned"}
        except MacroSourceError as exc:
            return {"healthy": False, "message": str(exc)}
        return {"healthy": False, "message": "Finnhub unavailable"}
