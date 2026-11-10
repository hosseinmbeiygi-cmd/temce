"""Finnhub market news and economic calendar provider.

Free-tier endpoints used here:
  GET /news              — market news (category: general|forex|crypto|merger)
  GET /calendar/earnings — upcoming earnings releases (1 month free)

Premium-only (not used by default):
  GET /calendar/economic — macro economic events (requires paid plan)

API base: ``https://finnhub.io/api/v1``
Auth: query param ``token=<FINNHUB_API_KEY>``
Rate limit: 60 requests / minute on all plans.
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

# Valid news categories for GET /news
NEWS_CATEGORIES = ("general", "forex", "crypto", "merger")


def _get_finnhub_key() -> str:
    return os.getenv("FINNHUB_API_KEY", "")


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FinnhubNewsItem:
    """One market news article from Finnhub GET /news."""

    headline: str
    summary: str
    url: str
    source: str
    category: str
    datetime_ts: int        # UNIX timestamp
    published_at: str       # ISO-8601 derived from datetime_ts
    image: str
    related: str            # related ticker symbol (if any)
    id: int
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class FinnhubEarning:
    """One earnings release from Finnhub GET /calendar/earnings."""

    symbol: str
    date: str               # YYYY-MM-DD
    hour: str               # "bmo" (before market open) | "amc" | "dmh" | ""
    eps_estimate: float | None
    eps_actual: float | None
    revenue_estimate: float | None
    revenue_actual: float | None
    quarter: int | None
    year: int | None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ── HTTP client ───────────────────────────────────────────────────────────────

class FinnhubClient:
    """Fetch Finnhub free-tier endpoints.

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
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._timeout_seconds = timeout_seconds

    def _require_key(self) -> str:
        if not self._api_key:
            raise MacroSourceError("FINNHUB_API_KEY is not configured")
        return self._api_key

    async def _get(self, path: str, params: dict) -> Any:
        close_client = self._client is None
        http = self._client or httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
        )
        try:
            resp = await http.get(f"{self._base_url}{path}", params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise MacroSourceError(
                f"Finnhub HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except Exception as exc:
            logger.warning("Finnhub fetch %s failed: %s", path, exc)
            return None
        finally:
            if close_client:
                await http.aclose()

    async def fetch_news(
        self,
        category: str = "general",
        min_id: int = 0,
    ) -> list[FinnhubNewsItem]:
        """Fetch market news (FREE tier).

        Args:
            category: ``"general"`` | ``"forex"`` | ``"crypto"`` | ``"merger"``
            min_id: return only articles with id > min_id (pagination).
        """
        key = self._require_key()
        if category not in NEWS_CATEGORIES:
            raise MacroSourceError(
                f"Invalid category '{category}'. Valid: {NEWS_CATEGORIES}"
            )
        payload = await self._get(
            "/news",
            params={"token": key, "category": category, "minId": min_id},
        )
        if not isinstance(payload, list):
            return []

        items: list[FinnhubNewsItem] = []
        for item in payload:
            ts = item.get("datetime", 0)
            published_at = (
                datetime.fromtimestamp(ts, tz=UTC).isoformat() if ts else ""
            )
            items.append(FinnhubNewsItem(
                headline    = item.get("headline", ""),
                summary     = item.get("summary", ""),
                url         = item.get("url", ""),
                source      = item.get("source", ""),
                category    = item.get("category", category),
                datetime_ts = ts,
                published_at= published_at,
                image       = item.get("image", ""),
                related     = item.get("related", ""),
                id          = item.get("id", 0),
            ))
        return items

    async def fetch_earnings_calendar(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        symbol: str | None = None,
    ) -> list[FinnhubEarning]:
        """Fetch earnings calendar (FREE: 1 month of data).

        Args:
            from_date: ``YYYY-MM-DD`` (default today).
            to_date:   ``YYYY-MM-DD`` (default +30 days).
            symbol:    filter by ticker (e.g. ``"AAPL"``).
        """
        key = self._require_key()
        today = date.today()
        params: dict[str, Any] = {
            "token": key,
            "from":  from_date or today.isoformat(),
            "to":    to_date   or (today + timedelta(days=30)).isoformat(),
        }
        if symbol:
            params["symbol"] = symbol

        payload = await self._get("/calendar/earnings", params=params)
        if not isinstance(payload, dict):
            return []

        raw: list[dict] = payload.get("earningsCalendar") or []
        results: list[FinnhubEarning] = []
        for ev in raw:
            results.append(FinnhubEarning(
                symbol           = ev.get("symbol", ""),
                date             = ev.get("date", ""),
                hour             = ev.get("hour", ""),
                eps_estimate     = _to_float(ev.get("epsEstimate")),
                eps_actual       = _to_float(ev.get("epsActual")),
                revenue_estimate = _to_float(ev.get("revenueEstimate")),
                revenue_actual   = _to_float(ev.get("revenueActual")),
                quarter          = _to_int(ev.get("quarter")),
                year             = _to_int(ev.get("year")),
            ))
        return results


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


# ── BaseProvider wrappers ─────────────────────────────────────────────────────

class FinnhubNewsProvider(BaseProvider):
    """Market news from Finnhub GET /news (FREE tier).

    Args:
        client: injectable httpx.AsyncClient for testing.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(name="finnhub_news")
        self._finnhub = FinnhubClient(client=client)

    async def fetch(
        self,
        category: str = "general",
        min_id: int = 0,
        limit: int = 50,
        **kwargs: Any,
    ) -> Result[Any]:
        """Return market news articles.

        Args:
            category: ``"general"`` | ``"forex"`` | ``"crypto"`` | ``"merger"``
            min_id:   pagination cursor (return articles with id > min_id).
            limit:    max items to return.
        """
        try:
            items = await self._finnhub.fetch_news(
                category=category,
                min_id=min_id,
            )
        except MacroSourceError as exc:
            return Result.fail(str(exc))

        if not items:
            return Result.fail("Finnhub returned no news articles")

        data = [
            {
                "id":           i.id,
                "headline":     i.headline,
                "summary":      i.summary,
                "url":          i.url,
                "source":       i.source,
                "category":     i.category,
                "published_at": i.published_at,
                "image":        i.image,
                "related":      i.related,
            }
            for i in items[:limit]
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        try:
            items = await self._finnhub.fetch_news(category="general")
            if items:
                return {"healthy": True, "message": f"{len(items)} articles"}
        except MacroSourceError as exc:
            return {"healthy": False, "message": str(exc)}
        return {"healthy": False, "message": "Finnhub news unavailable"}


class FinnhubEarningsProvider(BaseProvider):
    """Earnings calendar from Finnhub GET /calendar/earnings (FREE: 1 month).

    Args:
        client: injectable httpx.AsyncClient for testing.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(name="finnhub_earnings")
        self._finnhub = FinnhubClient(client=client)

    async def fetch(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        symbol: str | None = None,
        **kwargs: Any,
    ) -> Result[Any]:
        """Return upcoming earnings releases.

        Args:
            from_date: ``YYYY-MM-DD`` start.
            to_date:   ``YYYY-MM-DD`` end.
            symbol:    filter by ticker symbol.
        """
        try:
            items = await self._finnhub.fetch_earnings_calendar(
                from_date=from_date,
                to_date=to_date,
                symbol=symbol,
            )
        except MacroSourceError as exc:
            return Result.fail(str(exc))

        if not items:
            return Result.fail("Finnhub returned no earnings for the given range")

        data = [
            {
                "symbol":           i.symbol,
                "date":             i.date,
                "hour":             i.hour,
                "eps_estimate":     i.eps_estimate,
                "eps_actual":       i.eps_actual,
                "revenue_estimate": i.revenue_estimate,
                "revenue_actual":   i.revenue_actual,
                "quarter":          i.quarter,
                "year":             i.year,
            }
            for i in items
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        try:
            items = await self._finnhub.fetch_earnings_calendar()
            if items is not None:
                return {"healthy": True, "message": f"{len(items)} earnings events"}
        except MacroSourceError as exc:
            return {"healthy": False, "message": str(exc)}
        return {"healthy": False, "message": "Finnhub earnings unavailable"}


# ── Backward-compat alias ─────────────────────────────────────────────────────
# The old FinnhubProvider pointed at /calendar/economic (Premium-only).
# FinnhubNewsProvider is the drop-in replacement for free-tier use.
FinnhubProvider = FinnhubNewsProvider
