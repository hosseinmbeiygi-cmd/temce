"""Financial Modeling Prep (FMP) economic calendar provider.

API: ``https://financialmodelingprep.com/api/v3/economic_calendar``
Requires ``FMP_API_KEY`` environment variable.
Free tier: 250 requests/day.

Returns macro events with country, actual, estimate, and previous values.
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

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
DEFAULT_TIMEOUT_SECONDS: float = 10.0


def _get_fmp_key() -> str:
    return os.getenv("FMP_API_KEY", "")


@dataclass(frozen=True)
class FMPEvent:
    """One economic event from FMP."""

    event: str
    date: str              # ISO-8601 datetime string
    country: str
    actual: float | None
    previous: float | None
    change: float | None
    change_percent: float | None
    estimate: float | None
    impact: str            # "High" | "Medium" | "Low" | ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class FMPClient:
    """Fetch FMP economic calendar events.

    Inject ``client`` in tests to avoid real network calls.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = FMP_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or _get_fmp_key()
        self._base_url = base_url
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def fetch_calendar(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[FMPEvent]:
        """Fetch economic calendar in the given date range.

        Args:
            from_date: ``YYYY-MM-DD`` start (default: today).
            to_date: ``YYYY-MM-DD`` end (default: 7 days from today).
        """
        if not self._api_key:
            raise MacroSourceError("FMP_API_KEY is not configured")

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
                f"{self._base_url.rstrip('/')}/economic_calendar",
                params={"from": from_str, "to": to_str, "apikey": self._api_key},
            )
            resp.raise_for_status()
            raw: list[dict[str, Any]] = resp.json()
        except httpx.HTTPStatusError as exc:
            raise MacroSourceError(f"FMP HTTP {exc.response.status_code}") from exc
        except Exception as exc:
            logger.warning("FMP fetch failed: %s", exc)
            return []
        finally:
            if close_client:
                await http.aclose()

        events: list[FMPEvent] = []
        for ev in raw:
            events.append(FMPEvent(
                event          = ev.get("event", ""),
                date           = ev.get("date", ""),
                country        = ev.get("country", ""),
                actual         = _to_float(ev.get("actual")),
                previous       = _to_float(ev.get("previous")),
                change         = _to_float(ev.get("change")),
                change_percent = _to_float(ev.get("changePercentage")),
                estimate       = _to_float(ev.get("estimate")),
                impact         = ev.get("impact", ""),
            ))
        return events


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


class FMPProvider(BaseProvider):
    """Macro provider wrapping the FMP economic calendar API.

    Args:
        client: injectable httpx.AsyncClient for testing.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(name="fmp_calendar")
        self._fmp = FMPClient(client=client)

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
            country: filter by 2-letter ISO country code (e.g. ``"US"``).
        """
        try:
            events = await self._fmp.fetch_calendar(
                from_date=from_date,
                to_date=to_date,
            )
        except MacroSourceError as exc:
            return Result.fail(str(exc))

        if country:
            events = [e for e in events if e.country.upper() == country.upper()]

        if not events:
            return Result.fail("FMP returned no events for the given range")

        data = [
            {
                "event":          e.event,
                "date":           e.date,
                "country":        e.country,
                "actual":         e.actual,
                "previous":       e.previous,
                "change":         e.change,
                "change_percent": e.change_percent,
                "estimate":       e.estimate,
                "impact":         e.impact,
            }
            for e in events
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        try:
            events = await self._fmp.fetch_calendar()
            if events is not None:
                return {"healthy": True, "message": f"{len(events)} events returned"}
        except MacroSourceError as exc:
            return {"healthy": False, "message": str(exc)}
        return {"healthy": False, "message": "FMP unavailable"}
