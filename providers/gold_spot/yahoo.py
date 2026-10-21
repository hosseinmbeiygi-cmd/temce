"""Yahoo Finance gold futures provider (no paid API key required)."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

from providers.gold_spot.base import GoldSpotProvider, GoldSpotProviderError

DEFAULT_SYMBOL = "GC=F"
DEFAULT_BASE_URL = "https://query1.finance.yahoo.com"
DEFAULT_TIMEOUT_SECONDS = 5.0

_BROWSER_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


class YahooGoldSpotProvider(GoldSpotProvider):
    """Read ``regularMarketPrice`` from Yahoo's chart endpoint."""

    name = "yahoo"

    def __init__(
        self,
        *,
        symbol: str | None = None,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._symbol = symbol or os.environ.get("GOLD_FEED_YAHOO_SYMBOL", DEFAULT_SYMBOL)
        self._base_url = base_url or os.environ.get("GOLD_FEED_YAHOO_BASE_URL", DEFAULT_BASE_URL)
        self._client = client
        self._timeout_seconds = timeout_seconds

    def fetch(self) -> dict[str, Any]:
        path = f"/v8/finance/chart/{quote(self._symbol, safe='')}"
        url = f"{self._base_url.rstrip('/')}{path}"
        client, owned = self._get_client()
        try:
            response = client.get(
                url,
                params={"interval": "1m", "range": "1d"},
                headers=_BROWSER_HEADERS,
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if owned:
                client.close()

        try:
            result = payload["chart"]["result"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise GoldSpotProviderError(f"Yahoo chart response unusable: {exc}") from exc

        meta = result.get("meta") or {}
        price = meta.get("regularMarketPrice")
        timestamp = meta.get("regularMarketTime")

        if price is None:
            quotes = (result.get("indicators") or {}).get("quote") or []
            closes = quotes[0].get("close") if quotes else None
            if closes:
                price = next((value for value in reversed(closes) if value is not None), None)
        if timestamp is None:
            timestamps = result.get("timestamp") or []
            if timestamps:
                timestamp = timestamps[-1]

        if price is None or timestamp is None:
            raise GoldSpotProviderError("Yahoo chart response missing price or timestamp")

        price = float(price)
        if price <= 0:
            raise GoldSpotProviderError(f"Yahoo price must be positive, got {price!r}")

        return {"price": price, "timestamp": float(timestamp)}

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.Client(timeout=self._timeout_seconds, follow_redirects=True), True
