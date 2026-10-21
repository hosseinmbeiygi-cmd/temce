"""CFTC Commitment of Traders source client (disaggregated gold futures).

API: ``https://publicreporting.cftc.gov/resource/72hh-3qpy.json``
Open data (no auth required).  Dataset: Disaggregated Futures Only.
Gold futures contract market code: ``088691`` (COMEX Gold).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

from providers.macro_sources.base import MacroSourceError, MacroSourceProvider

CFTC_GOLD_CONTRACT_MARKET_CODE = "088691"
CFTC_DATASET_ID = "72hh-3qpy"
DEFAULT_CFTC_BASE_URL = "https://publicreporting.cftc.gov"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_LOOKBACK_WEEKS = 52

# Candidate source field names for managed-money long/short (disaggregated).
_MM_LONG_CANDIDATES = (
    "m_money_positions_long_all",
    "managed_money_long",
)
_MM_SHORT_CANDIDATES = (
    "m_money_positions_short_all",
    "managed_money_short",
)
_COMM_LONG_CANDIDATES = (
    "prod_merc_positions_long_all",
    "prod_merc_positions_long",
    "commercial_long",
)
_COMM_SHORT_CANDIDATES = (
    "prod_merc_positions_short_all",
    "prod_merc_positions_short",
    "commercial_short",
)
_OI_CANDIDATES = ("open_interest_all", "open_interest")


class CFTCClient(MacroSourceProvider):
    """Read CFTC COT disaggregated gold futures reports."""

    name = "CFTC"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        contract_market_code: str = CFTC_GOLD_CONTRACT_MARKET_CODE,
        lookback_weeks: int = DEFAULT_LOOKBACK_WEEKS,
    ) -> None:
        self._base_url = base_url or DEFAULT_CFTC_BASE_URL
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._contract_market_code = contract_market_code
        self._lookback_weeks = lookback_weeks

    def fetch(self) -> list[dict[str, Any]]:
        """Return recent weekly COT gold reports (newest first)."""
        client, owned = self._get_client()
        try:
            url = f"{self._base_url.rstrip('/')}/resource/{CFTC_DATASET_ID}.json"
            params = {
                "$where": f"cftc_contract_market_code='{self._contract_market_code}'",
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": self._lookback_weeks,
            }
            try:
                response = client.get(url, params=params, timeout=self._timeout_seconds)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise MacroSourceError(f"CFTC COT HTTP {exc.response.status_code}") from exc
            except httpx.RequestError as exc:  # pragma: no cover - network
                raise MacroSourceError(f"CFTC COT request failed: {exc}") from exc

            try:
                rows = response.json()
            except ValueError as exc:
                raise MacroSourceError("CFTC COT returned invalid JSON") from exc

            if not isinstance(rows, list):
                raise MacroSourceError("CFTC COT response is not a list")

            observations: list[dict[str, Any]] = []
            for row in rows:
                obs = self._parse_row(row)
                if obs is not None:
                    observations.append(obs)
            return observations
        finally:
            if owned:
                client.close()

    def _parse_row(self, row: dict[str, Any]) -> dict[str, Any] | None:
        raw_date = row.get("report_date_as_yyyy_mm_dd")
        if raw_date is None:
            return None
        observation_date = self._parse_date(raw_date)
        if observation_date is None:
            return None

        long_val = self._pick_int(row, _MM_LONG_CANDIDATES)
        short_val = self._pick_int(row, _MM_SHORT_CANDIDATES)
        comm_long = self._pick_int(row, _COMM_LONG_CANDIDATES)
        comm_short = self._pick_int(row, _COMM_SHORT_CANDIDATES)
        oi = self._pick_int(row, _OI_CANDIDATES)

        m_money_net = None
        if long_val is not None and short_val is not None:
            m_money_net = long_val - short_val
        comm_net = None
        if comm_long is not None and comm_short is not None:
            comm_net = comm_long - comm_short

        # Week-on-week change in managed-money net.
        net_change = None
        change_long = self._pick_int(row, ("change_in_m_money_long_all",))
        change_short = self._pick_int(row, ("change_in_m_money_short_all",))
        if change_long is not None and change_short is not None:
            net_change = change_long - change_short

        return {
            "observation_date": observation_date,
            "report_date": str(observation_date),
            "value": float(m_money_net) if m_money_net is not None else None,
            "previous_value": None,
            "change": float(net_change) if net_change is not None else None,
            "managed_money_long": long_val,
            "managed_money_short": short_val,
            "managed_money_net": m_money_net,
            "managed_money_net_change": net_change,
            "commercial_long": comm_long,
            "commercial_short": comm_short,
            "commercial_net": comm_net,
            "open_interest": oi,
            "market_name": row.get("market_and_exchange_names") or row.get("contract_market_name"),
            "provenance": {
                "provider": "CFTC",
                "dataset": CFTC_DATASET_ID,
                "cftc_contract_market_code": self._contract_market_code,
                "url": "https://publicreporting.cftc.gov/resource/72hh-3qpy.json",
            },
        }

    @staticmethod
    def _parse_date(raw: Any) -> date | None:
        if isinstance(raw, date) and not isinstance(raw, datetime):
            return raw
        if isinstance(raw, str):
            raw = raw[:10]
            try:
                return date.fromisoformat(raw)
            except ValueError:
                return None
        return None

    @staticmethod
    def _pick_int(row: dict[str, Any], candidates: tuple[str, ...]) -> int | None:
        for name in candidates:
            value = row.get(name)
            if value is None or value == "":
                continue
            try:
                return int(float(value))
            except (TypeError, ValueError):
                continue
        return None

    def _get_client(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        return httpx.Client(timeout=self._timeout_seconds, follow_redirects=True), True


def build_default_cftc_client() -> CFTCClient:
    """Return a production CFTC client (open data, no key required)."""
    return CFTCClient()
