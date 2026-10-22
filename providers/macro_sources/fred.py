"""FRED macro source client (10Y TIPS real yield + broad dollar index).

API: ``https://api.stlouisfed.org/fred/series/observations``
Requires ``FRED_API_KEY`` environment variable.
"""

from __future__ import annotations

from typing import Any

import httpx

from providers.macro_sources.base import MacroSourceError, MacroSourceProvider, _env_api_key, _to_float

FRED_TIPS_10Y_SERIES = "DFII10"   # 10-Year Treasury Inflation-Indexed Constant Maturity (percent)
FRED_DXY_BROAD_SERIES = "DTWEXBGS"  # Nominal Broad U.S. Dollar Index (index)

DEFAULT_FRED_BASE_URL = "https://api.stlouisfed.org"
DEFAULT_TIMEOUT_SECONDS = 10.0


def _settings_api_key() -> str:
    """Fall back to the repository ``.env`` via ``core.config.Settings``.

    Jobs/scripts import this provider directly; they should not need to call
    ``load_dotenv`` just to read ``FRED_API_KEY``.
    """
    try:
        from core.config import get_settings

        return get_settings().fred_api_key
    except Exception:  # pragma: no cover - settings are optional for tests
        return ""


class FREDClient(MacroSourceProvider):
    """Read FRED series observations with an injectable ``httpx.Client``.

    ``FRED_API_KEY`` must be set (via env) or passed explicitly; otherwise
    ``fetch()`` raises ``MacroSourceError`` so the sync job can fail back.
    """

    name = "FRED"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if api_key is None:
            api_key = _env_api_key("FRED_API_KEY") or _settings_api_key()
        self._api_key = api_key
        self._base_url = base_url or DEFAULT_FRED_BASE_URL
        self._client = client
        self._timeout_seconds = timeout_seconds

    def _require_key(self) -> None:
        if not self._api_key:
            raise MacroSourceError("FRED API key is not configured (set FRED_API_KEY)")

    def fetch(self) -> list[dict[str, Any]]:
        """Fetch the latest observation for TIPS 10Y and the broad dollar index."""
        self._require_key()
        client, owned = self._get_client()
        observations: list[dict[str, Any]] = []
        try:
            for series_id in (FRED_TIPS_10Y_SERIES, FRED_DXY_BROAD_SERIES):
                obs = self._fetch_series(client, series_id)
                if obs is not None:
                    observations.append(obs)
        finally:
            if owned:
                client.close()
        return observations

    def fetch_series(self, series_id: str) -> dict[str, Any] | None:
        """Fetch the latest observation for a single FRED series."""
        self._require_key()
        client, owned = self._get_client()
        try:
            return self._fetch_series(client, series_id)
        finally:
            if owned:
                client.close()

    def fetch_range(
        self,
        series_id: str,
        *,
        observation_start: str,
        observation_end: str | None = None,
        limit: int = 100_000,
    ) -> list[dict[str, Any]]:
        """Fetch every valid observation in ``[observation_start, end]``.

        Used by the one-shot gold-macro backfill.  FRED returns ``"."`` for
        holidays; those rows are skipped rather than coerced to zero.
        """
        self._require_key()
        params: dict[str, Any] = {
            "observation_start": str(observation_start),
            "sort_order": "asc",
            "limit": int(limit),
        }
        if observation_end is not None:
            params["observation_end"] = str(observation_end)

        client, owned = self._get_client()
        try:
            observations, source_url = self._request_observations(
                client, series_id, params=params
            )
        finally:
            if owned:
                client.close()

        rows: list[dict[str, Any]] = []
        for observation in observations:
            value = _to_float(observation.get("value"))
            if value is None:
                continue
            rows.append(
                {
                    "observation_date": observation.get("date"),
                    "value": value,
                    "previous_value": None,
                    "change": None,
                    "series_id": series_id,
                    "provenance": {
                        "provider": "FRED",
                        "series_id": series_id,
                        "url": source_url,
                    },
                }
            )
        return rows

    def _fetch_series(self, client: httpx.Client, series_id: str) -> dict[str, Any] | None:
        observations, source_url = self._request_observations(
            client,
            series_id,
            params={"sort_order": "desc", "limit": 1},
        )
        if not observations:
            return None

        latest = observations[0]
        observation_date = latest.get("date")
        value = _to_float(latest.get("value"))
        if value is None:
            return None

        return {
            "observation_date": observation_date,
            "value": value,
            "previous_value": None,
            "change": None,
            "series_id": series_id,
            "provenance": {
                "provider": "FRED",
                "series_id": series_id,
                "url": source_url,
            },
        }

    def _request_observations(
        self,
        client: httpx.Client,
        series_id: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        url = f"{self._base_url.rstrip('/')}/fred/series/observations"
        request_params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
        }
        if params:
            request_params.update(params)
        try:
            response = client.get(
                url,
                params=request_params,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MacroSourceError(f"FRED {series_id} HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:  # pragma: no cover - network
            raise MacroSourceError(f"FRED {series_id} request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise MacroSourceError(f"FRED {series_id} returned invalid JSON") from exc

        observations = payload.get("observations") or []
        source_url = str(response.url).replace(self._api_key or "", "REDACTED")
        return observations, source_url

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.Client(timeout=self._timeout_seconds, follow_redirects=True), True


# ── Convenience constructors ────────────────────────────────────────────


def build_default_fred_client() -> FREDClient:
    """Return a production FRED client (env var, then repository ``.env``)."""
    return FREDClient()
