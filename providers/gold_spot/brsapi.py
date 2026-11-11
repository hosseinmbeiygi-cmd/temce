"""BrsApi gold spot provider (XAUUSD, USD per troy ounce)."""

from __future__ import annotations

from typing import Any

import httpx

from brsapi.config import BrsApiEndpoints
from brsapi.config import settings as brsapi_settings
from brsapi.parsers.commodity import GoldCurrencyProParser
from providers.gold_spot.base import GoldSpotProvider, GoldSpotProviderError

DEFAULT_TIMEOUT_SECONDS = 5.0

# BrsApi's edge expects a browser-like request; the shared async client sets
# these too, but this provider uses a synchronous client for the feed executor.
_BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://brsapi.ir/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


class BrsApiGoldSpotProvider(GoldSpotProvider):
    """Read the ``gold`` section of ``/Market/Gold_Currency_Pro.php``."""

    name = "brsapi"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        enabled: bool | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._enabled = enabled

    def fetch(self) -> dict[str, Any]:
        enabled = brsapi_settings.enabled if self._enabled is None else self._enabled
        if not enabled:
            raise GoldSpotProviderError("BrsApi is disabled by configuration")

        api_key = self._api_key if self._api_key is not None else brsapi_settings.api_key
        if not api_key:
            raise GoldSpotProviderError("BrsApi API key is not configured")

        base_url = (self._base_url or brsapi_settings.base_url).rstrip("/")
        url = f"{base_url}{BrsApiEndpoints.GOLD_CURRENCY_PRO.path}"
        client, owned = self._get_client()
        try:
            response = client.get(
                url,
                params={"key": api_key, "section": "gold"},
                headers=_BROWSER_HEADERS,
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if owned:
                client.close()

        rows = GoldCurrencyProParser.parse_gold(payload)
        row = next(
            (item for item in rows if str(item.get("symbol", "")).upper() == "XAUUSD"),
            None,
        )
        if row is None:
            raise GoldSpotProviderError("BrsApi gold response missing XAUUSD")

        price = float(row.get("price") or 0.0)
        if price <= 0:
            raise GoldSpotProviderError(f"BrsApi XAUUSD price must be positive, got {price!r}")

        timestamp = float(row.get("time_unix") or 0.0)
        if timestamp <= 0:
            raise GoldSpotProviderError("BrsApi XAUUSD quote missing timestamp")

        return {"price": price, "timestamp": timestamp}

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.Client(timeout=self._timeout_seconds, follow_redirects=True), True
