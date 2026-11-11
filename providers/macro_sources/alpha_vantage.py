"""Alpha Vantage macro-economic indicator provider.

Free-tier endpoints used (no API key rate limit beyond 25 req/day):
  TREASURY_YIELD      — 10-year US Treasury yield (inverse-correlated with gold)
  FEDERAL_FUNDS_RATE  — Fed funds rate (monetary policy signal)
  CPI                 — Consumer Price Index monthly (inflation proxy)
  INFLATION           — Annual inflation rate
  UNEMPLOYMENT        — Unemployment rate
  NONFARM_PAYROLL     — Non-farm payroll monthly

NOTE: NEWS_SENTIMENT is a Premium endpoint and is NOT used here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.macro_sources.base import MacroSourceError

logger = get_logger(__name__)

AV_BASE_URL = "https://www.alphavantage.co/query"
DEFAULT_TIMEOUT_SECONDS: float = 15.0

# Free macro indicator definitions: (function, interval, label_en, label_fa)
MACRO_INDICATORS: list[tuple[str, str, str, str]] = [
    ("TREASURY_YIELD",     "monthly",  "US 10Y Treasury Yield",    "بازده اوراق خزانه ۱۰ ساله"),
    ("FEDERAL_FUNDS_RATE", "monthly",  "Federal Funds Rate",       "نرخ بهره فدرال"),
    ("CPI",                "monthly",  "CPI (Inflation)",          "شاخص قیمت مصرف‌کننده"),
    ("INFLATION",          "annual",   "Annual Inflation Rate",    "نرخ تورم سالانه"),
    ("UNEMPLOYMENT",       "monthly",  "Unemployment Rate",        "نرخ بیکاری"),
    ("NONFARM_PAYROLL",    "monthly",  "Non-Farm Payroll",         "اشتغال غیرکشاورزی"),
]


def _get_av_key() -> str:
    return os.getenv("ALPHA_VANTAGE_API_KEY", "")


@dataclass(frozen=True)
class AVMacroPoint:
    """One data point from a macro time series."""

    indicator: str       # e.g. "TREASURY_YIELD"
    label_en: str
    label_fa: str
    date: str            # YYYY-MM-DD
    value: float | None
    unit: str            # e.g. "percent"
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AlphaVantageMacroClient:
    """Fetch free macro-economic indicators from Alpha Vantage.

    Inject ``client`` in tests to avoid real network calls.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = AV_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or _get_av_key()
        self._base_url = base_url
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def _fetch_series(
        self,
        http: httpx.AsyncClient,
        function: str,
        interval: str,
        label_en: str,
        label_fa: str,
        limit: int = 3,
    ) -> list[AVMacroPoint]:
        """Fetch the latest ``limit`` data points for one indicator."""
        params: dict[str, Any] = {
            "function": function,
            "interval": interval,
            "apikey":   self._api_key,
        }
        try:
            resp = await http.get(self._base_url, params=params, timeout=self._timeout_seconds)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("AlphaVantage %s HTTP %d", function, exc.response.status_code)
            return []
        except Exception as exc:
            logger.warning("AlphaVantage %s fetch error: %s", function, exc)
            return []

        if "Information" in payload or "Note" in payload:
            msg = payload.get("Information") or payload.get("Note", "")
            logger.warning("AlphaVantage %s: %s", function, msg)
            raise MacroSourceError(f"AlphaVantage quota/key issue: {msg}")

        # All free indicators share the same envelope: {"name":..., "unit":..., "data":[...]}
        data_rows: list[dict[str, Any]] = payload.get("data") or []
        unit = payload.get("unit", "")
        points: list[AVMacroPoint] = []
        for row in data_rows[:limit]:
            raw_val = row.get("value")
            try:
                value = float(raw_val) if raw_val not in (None, ".", "") else None
            except (ValueError, TypeError):
                value = None
            points.append(AVMacroPoint(
                indicator = function,
                label_en  = label_en,
                label_fa  = label_fa,
                date      = str(row.get("date", "")),
                value     = value,
                unit      = unit,
            ))
        return points

    async def fetch_macro_indicators(self, limit_per_series: int = 3) -> list[AVMacroPoint]:
        """Fetch the latest data points for all free macro indicators.

        Args:
            limit_per_series: how many recent data points per indicator (default 3).
        Returns:
            flat list of AVMacroPoint, all indicators, newest first within each.
        Raises:
            MacroSourceError: if the API key is missing or quota exceeded.
        """
        if not self._api_key:
            raise MacroSourceError("ALPHA_VANTAGE_API_KEY is not configured")

        import asyncio

        close_client = self._client is None
        http = self._client or httpx.AsyncClient(follow_redirects=True)
        try:
            tasks = [
                self._fetch_series(http, fn, interval, label_en, label_fa, limit_per_series)
                for fn, interval, label_en, label_fa in MACRO_INDICATORS
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            if close_client:
                await http.aclose()

        all_points: list[AVMacroPoint] = []
        for result in results:
            if isinstance(result, MacroSourceError):
                raise result
            if isinstance(result, list):
                all_points.extend(result)
        return all_points


# ── Backward-compat shim: AlphaVantageNewsClient ─────────────────────────────
# The old NEWS_SENTIMENT endpoint is Premium and was removed. This stub
# preserves the class name so existing imports don't break.

class AlphaVantageNewsClient(AlphaVantageMacroClient):
    """Deprecated: NEWS_SENTIMENT is Premium. Use AlphaVantageMacroClient."""

    async def fetch_gold_news(self, **_kwargs: Any) -> list[Any]:  # type: ignore[override]
        logger.warning(
            "AlphaVantageNewsClient.fetch_gold_news() called — "
            "NEWS_SENTIMENT is a Premium endpoint; "
            "use AlphaVantageMacroClient.fetch_macro_indicators() instead."
        )
        return []


# ── BaseProvider wrapper ──────────────────────────────────────────────────────

class AlphaVantageMacroProvider(BaseProvider):
    """Free macro-economic indicators provider using Alpha Vantage."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(name="alpha_vantage_macro")
        self._av = AlphaVantageMacroClient(client=client)

    async def fetch(
        self,
        limit_per_series: int = 3,
        **kwargs: Any,
    ) -> Result[Any]:
        try:
            points = await self._av.fetch_macro_indicators(limit_per_series=limit_per_series)
        except MacroSourceError as exc:
            return Result.fail(str(exc))

        if not points:
            return Result.fail("AlphaVantage returned no macro data")

        data = [
            {
                "indicator":   p.indicator,
                "label_en":    p.label_en,
                "label_fa":    p.label_fa,
                "date":        p.date,
                "value":       p.value,
                "unit":        p.unit,
                "fetched_at":  p.fetched_at.isoformat(),
            }
            for p in points
        ]
        return Result.ok(data)

    async def health(self) -> dict[str, Any]:
        try:
            points = await self._av.fetch_macro_indicators(limit_per_series=1)
            if points:
                return {"healthy": True, "message": f"{len(points)} indicators fetched"}
        except MacroSourceError as exc:
            return {"healthy": False, "message": str(exc)}
        return {"healthy": False, "message": "AlphaVantage unavailable"}


# Backward-compat alias — old code imported AlphaVantageNewsProvider
AlphaVantageNewsProvider = AlphaVantageMacroProvider
