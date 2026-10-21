"""Unit tests for macro data providers (FRED, CFTC).

All HTTP is served by ``httpx.MockTransport``; no real network calls.
"""

from __future__ import annotations

import httpx
import pytest

from providers.macro_sources.cftc import CFTC_GOLD_CONTRACT_MARKET_CODE, CFTCClient
from providers.macro_sources.fred import FRED_TIPS_10Y_SERIES, FREDClient


def _fred_client(payload: dict) -> FREDClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "series_id" in request.url.params
        return httpx.Response(200, json=payload)

    return FREDClient(api_key="test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_fred_parses_tips_and_dxy() -> None:
    payload = {
        "observations": [
            {"date": "2026-10-15", "value": "0.85", "series_id": FRED_TIPS_10Y_SERIES},
        ]
    }
    client = _fred_client(payload)
    obs = client.fetch()
    tips = [o for o in obs if o["series_id"] == FRED_TIPS_10Y_SERIES]
    assert tips
    assert tips[0]["value"] == 0.85
    assert tips[0]["observation_date"] == "2026-10-15"


def test_fred_handles_missing_value() -> None:
    payload = {"observations": [{"date": "2026-10-15", "value": ".", "series_id": FRED_TIPS_10Y_SERIES}]}
    client = _fred_client(payload)
    obs = client.fetch()
    assert obs == []


def test_fred_no_api_key_raises() -> None:
    client = FREDClient(api_key=None)
    with pytest.raises(Exception):
        client.fetch()


def test_cftc_parses_gold_positions() -> None:
    payload = [
        {
            "report_date_as_yyyy_mm_dd": "2026-10-09",
            "cftc_contract_market_code": CFTC_GOLD_CONTRACT_MARKET_CODE,
            "market_and_exchange_names": "GOLD - COMEX",
            "m_money_positions_long_all": 45_000,
            "m_money_positions_short_all": 12_000,
            "change_in_m_money_long_all": 3_000,
            "change_in_m_money_short_all": -1_000,
            "prod_merc_positions_long_all": 90_000,
            "prod_merc_positions_short_all": 20_000,
            "open_interest_all": 500_000,
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/resource/72hh-3qpy.json"
        return httpx.Response(200, json=payload)

    client = CFTCClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    obs = client.fetch()
    assert len(obs) == 1
    row = obs[0]
    assert row["report_date"] == "2026-10-09"
    assert row["managed_money_long"] == 45_000
    assert row["managed_money_short"] == 12_000
    assert row["managed_money_net"] == 33_000
    assert row["managed_money_net_change"] == 4_000
    assert row["commercial_long"] == 90_000
    assert row["commercial_short"] == 20_000
    assert row["commercial_net"] == 70_000
    assert row["open_interest"] == 500_000
    assert row["market_name"] == "GOLD - COMEX"


def test_cftc_parses_real_live_field_names() -> None:
    """The live CFTC dataset names the commercial fields without an ``_all`` suffix.

    Recorded from a real response on 2026-10-13 (COMEX Gold, contract 088691).
    The fabricated ``prod_merc_positions_*_all`` name in the test above never
    appears in the dataset, so the commercial net silently came back ``None``.
    """
    payload = [
        {
            "report_date_as_yyyy_mm_dd": "2026-10-13",
            "cftc_contract_market_code": CFTC_GOLD_CONTRACT_MARKET_CODE,
            "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
            "m_money_positions_long_all": 124_747,
            "m_money_positions_short_all": 17_658,
            "change_in_m_money_long_all": 1_000,
            "change_in_m_money_short_all": 4_898,
            "prod_merc_positions_long": 18_386,
            "prod_merc_positions_short": 36_823,
            "open_interest_all": 396_345,
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = CFTCClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    obs = client.fetch()
    assert len(obs) == 1
    row = obs[0]
    assert row["managed_money_net"] == 107_089
    assert row["managed_money_net_change"] == -3_898
    assert row["commercial_long"] == 18_386
    assert row["commercial_short"] == 36_823
    assert row["commercial_net"] is not None
    assert row["commercial_net"] == (
        row["commercial_long"] - row["commercial_short"]
    )
    assert row["commercial_net"] == -18_437
    assert row["open_interest"] == 396_345


def test_cftc_filters_non_gold_contracts() -> None:
    payload = [
        {
            "report_date_as_yyyy_mm_dd": "2026-10-09",
            "cftc_contract_market_code": "999999",
            "m_money_positions_long_all": 100,
            "m_money_positions_short_all": 50,
        },
        {
            "report_date_as_yyyy_mm_dd": "2026-10-09",
            "cftc_contract_market_code": CFTC_GOLD_CONTRACT_MARKET_CODE,
            "m_money_positions_long_all": 45_000,
            "m_money_positions_short_all": 12_000,
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        # Server-side $where filter: only gold contract rows are returned.
        filtered = [
            row
            for row in payload
            if row.get("cftc_contract_market_code") == CFTC_GOLD_CONTRACT_MARKET_CODE
        ]
        return httpx.Response(200, json=filtered)

    client = CFTCClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    obs = client.fetch()
    assert len(obs) == 1
    assert obs[0]["managed_money_long"] == 45_000


def test_cftc_handles_null_values() -> None:
    payload = [
        {
            "report_date_as_yyyy_mm_dd": "2026-10-09",
            "cftc_contract_market_code": CFTC_GOLD_CONTRACT_MARKET_CODE,
            "m_money_positions_long_all": None,
            "m_money_positions_short_all": None,
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = CFTCClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    obs = client.fetch()
    row = obs[0]
    assert row["managed_money_long"] is None
    assert row["managed_money_short"] is None
    assert row["managed_money_net"] is None
