"""WS13: Extended FRED series — TDD tests.

RED phase verifies:
  1. FRED_SERIES_META dict is importable from providers.macro_sources.fred.
  2. All 14 gold-relevant series are present in the meta dict.
  3. Each series has correct unit/frequency metadata.
  4. FREDClient.fetch() now requests every series in FRED_SERIES_META.
  5. _upsert_macro_indicator uses FRED_SERIES_META for unit (not a hard-coded
     per-series branch).

GREEN phase:
  - Add FRED_SERIES_META to fred.py and update fetch() / _upsert_macro_indicator.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ─── 1. FRED_SERIES_META import ──────────────────────────────────────────────

def test_fred_series_meta_is_importable():
    """FRED_SERIES_META must exist and be a dict.

    RED: not yet defined.
    GREEN: added to providers.macro_sources.fred.
    """
    from providers.macro_sources.fred import FRED_SERIES_META
    assert isinstance(FRED_SERIES_META, dict)
    assert len(FRED_SERIES_META) >= 14


# ─── 2. Series constants ──────────────────────────────────────────────────────

def test_new_series_constants_importable():
    """All new series-id constants must be importable.

    RED: constants not yet defined.
    GREEN: added alongside existing FRED_TIPS_10Y_SERIES / FRED_DXY_BROAD_SERIES.
    """
    from providers.macro_sources.fred import (  # noqa: F401
        FRED_CPI_SERIES,
        FRED_DGS10_SERIES,
        FRED_DGS2_SERIES,
        FRED_DGS30_SERIES,
        FRED_FEDERAL_DEBT_SERIES,
        FRED_FEDFUNDS_SERIES,
        FRED_GDP_SERIES,
        FRED_GOLD_AM_FIX_SERIES,
        FRED_GOLD_PM_FIX_SERIES,
        FRED_M2_SERIES,
        FRED_NFP_SERIES,
        FRED_PCE_SERIES,
        FRED_PPI_SERIES,
        FRED_SILVER_FIX_SERIES,
        FRED_UNEMPLOYMENT_SERIES,
    )


def test_new_series_constants_have_correct_values():
    """Verify series-id strings match FRED IDs used by STLOUISFED.

    RED: constants missing.
    GREEN: each constant equals the official FRED series identifier.
    """
    from providers.macro_sources.fred import (
        FRED_CPI_SERIES,
        FRED_DGS10_SERIES,
        FRED_DGS2_SERIES,
        FRED_DGS30_SERIES,
        FRED_FEDERAL_DEBT_SERIES,
        FRED_FEDFUNDS_SERIES,
        FRED_GDP_SERIES,
        FRED_M2_SERIES,
        FRED_NFP_SERIES,
        FRED_PCE_SERIES,
        FRED_PPI_SERIES,
        FRED_UNEMPLOYMENT_SERIES,
    )
    assert FRED_DGS10_SERIES == "DGS10"
    assert FRED_DGS2_SERIES == "DGS2"
    assert FRED_DGS30_SERIES == "DGS30"
    assert FRED_FEDFUNDS_SERIES == "FEDFUNDS"
    assert FRED_CPI_SERIES == "CPIAUCSL"
    assert FRED_PPI_SERIES == "PPIACO"
    assert FRED_NFP_SERIES == "PAYEMS"
    assert FRED_UNEMPLOYMENT_SERIES == "UNRATE"
    assert FRED_GDP_SERIES == "GDP"
    assert FRED_PCE_SERIES == "PCEPI"
    assert FRED_M2_SERIES == "M2SL"
    assert FRED_FEDERAL_DEBT_SERIES == "GFDEBTN"


# ─── 3. FRED_SERIES_META: required series present ────────────────────────────

REQUIRED_SERIES = {
    "DFII10", "DTWEXBGS",                              # original two
    "DGS10", "DGS2", "DGS30",                         # Treasury yields
    "FEDFUNDS",                                         # Fed funds
    "CPIAUCSL", "PPIACO",                              # CPI / PPI
    "PAYEMS", "UNRATE",                                # Labour
    "GDP", "PCEPI",                                    # GDP / PCE
    "M2SL", "GFDEBTN",                                # Money supply / Federal debt
    "GOLDAMGBD228NLBM", "GOLDPMGBD228NLBM", "SLVPRUSD",  # LBMA historical prices
}


def test_fred_series_meta_contains_all_required_series():
    """FRED_SERIES_META must include every gold-relevant series.

    RED: FRED_SERIES_META not yet defined.
    GREEN: dict populated with 14 entries.
    """
    from providers.macro_sources.fred import FRED_SERIES_META

    missing = REQUIRED_SERIES - set(FRED_SERIES_META.keys())
    assert not missing, f"Missing series in FRED_SERIES_META: {missing}"


# ─── 4. FRED_SERIES_META: unit field correctness ─────────────────────────────

@pytest.mark.parametrize("series_id,expected_unit", [
    ("DFII10",             "percent"),
    ("DTWEXBGS",           "index"),
    ("DGS10",              "percent"),
    ("DGS2",               "percent"),
    ("DGS30",              "percent"),
    ("FEDFUNDS",           "percent"),
    ("UNRATE",             "percent"),
    ("CPIAUCSL",           "index"),
    ("PPIACO",             "index"),
    ("PCEPI",              "index"),
    ("PAYEMS",             "thousands"),
    ("GDP",                "billions_usd"),
    ("M2SL",               "billions_usd"),
    ("GFDEBTN",            "millions_usd"),
    ("GOLDAMGBD228NLBM",   "usd_per_oz"),
    ("GOLDPMGBD228NLBM",   "usd_per_oz"),
    ("SLVPRUSD",           "usd_per_oz"),
])
def test_fred_series_meta_unit(series_id: str, expected_unit: str):
    """Each series in FRED_SERIES_META must carry the correct 'unit' string.

    RED: FRED_SERIES_META not yet defined.
    GREEN: metadata populated correctly.
    """
    from providers.macro_sources.fred import FRED_SERIES_META

    meta = FRED_SERIES_META.get(series_id)
    assert meta is not None, f"{series_id} not in FRED_SERIES_META"
    assert meta.get("unit") == expected_unit, (
        f"{series_id}: expected unit={expected_unit!r}, got {meta.get('unit')!r}"
    )


# ─── 5. FREDClient.fetch() now requests all meta series ──────────────────────

def _make_mock_response(series_id: str, value: float = 1.0) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}"
    resp.json.return_value = {
        "observations": [{"date": "2026-10-01", "value": str(value)}]
    }
    resp.raise_for_status.return_value = None
    return resp


def test_fred_fetch_requests_all_meta_series():
    """FREDClient.fetch() must issue one request per series in FRED_SERIES_META.

    RED: fetch() currently only requests DFII10 and DTWEXBGS.
    GREEN: fetch() iterates over all FRED_SERIES_META keys.
    """
    from providers.macro_sources.fred import FRED_SERIES_META, FREDClient

    mock_client = MagicMock()
    # Return a valid single-observation response for every series.
    mock_client.get.side_effect = lambda url, **kw: _make_mock_response(
        kw.get("params", {}).get("series_id", "UNKNOWN")
    )

    fred = FREDClient(api_key="test-key", client=mock_client)
    observations = fred.fetch()

    fetched_series = {obs["series_id"] for obs in observations}
    missing = set(FRED_SERIES_META.keys()) - fetched_series
    assert not missing, f"fetch() did not retrieve: {missing}"
    assert mock_client.get.call_count == len(FRED_SERIES_META)


def test_fred_fetch_returns_observation_for_each_series():
    """fetch() returns one observation dict per series with correct series_id.

    RED: fetch() only returns 2 observations (DFII10 + DTWEXBGS).
    GREEN: returns len(FRED_SERIES_META) observations.
    """
    from providers.macro_sources.fred import FRED_SERIES_META, FREDClient

    mock_client = MagicMock()
    mock_client.get.side_effect = lambda url, **kw: _make_mock_response(
        kw.get("params", {}).get("series_id", "UNKNOWN")
    )

    fred = FREDClient(api_key="test-key", client=mock_client)
    observations = fred.fetch()

    assert len(observations) == len(FRED_SERIES_META)
    for obs in observations:
        assert obs["series_id"] in FRED_SERIES_META


# ─── 6. MacroSyncService._upsert_macro_indicator uses metadata unit ───────────

def _obs(series_id: str, date_str: str = "2026-10-01", value: float = 1.0) -> dict[str, Any]:
    return {
        "series_id": series_id,
        "observation_date": date_str,
        "value": value,
        "previous_value": None,
        "change": None,
        "provenance": {"provider": "FRED", "series_id": series_id},
    }


def _make_session() -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    session.execute = MagicMock(return_value=result)
    # Make execute awaitable
    from unittest.mock import AsyncMock
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_upsert_uses_percent_for_dgs10():
    """_upsert_macro_indicator stores unit='percent' for DGS10 (not 'index').

    RED: _upsert_macro_indicator currently uses 'index' for every non-DFII10 series.
    GREEN: unit comes from FRED_SERIES_META → 'percent' for DGS10.
    """
    from services.gold.macro_sync import MacroSyncService

    session = _make_session()
    added_rows: list[Any] = []
    session.add.side_effect = added_rows.append

    fred = MagicMock()
    fred.fetch.return_value = [_obs("DGS10", value=4.5)]
    service = MacroSyncService(session, fred_provider=fred)

    from providers.macro_sources.fred import FRED_SERIES_META
    all_ids = tuple(FRED_SERIES_META.keys())
    result = await service.sync_fred_indicators(indicators=all_ids)

    assert result.upserted == 1
    row = added_rows[0]
    assert row.unit == "percent", f"Expected unit='percent', got {row.unit!r}"


@pytest.mark.asyncio
async def test_upsert_uses_billions_usd_for_gdp():
    """_upsert_macro_indicator stores unit='billions_usd' for GDP series.

    RED: _upsert_macro_indicator uses 'index' as fallback for all non-DFII10 series.
    GREEN: unit comes from FRED_SERIES_META → 'billions_usd' for GDP.
    """
    from services.gold.macro_sync import MacroSyncService

    session = _make_session()
    added_rows: list[Any] = []
    session.add.side_effect = added_rows.append

    fred = MagicMock()
    fred.fetch.return_value = [_obs("GDP", value=28_000.0)]
    service = MacroSyncService(session, fred_provider=fred)

    from providers.macro_sources.fred import FRED_SERIES_META
    all_ids = tuple(FRED_SERIES_META.keys())
    result = await service.sync_fred_indicators(indicators=all_ids)

    assert result.upserted == 1
    row = added_rows[0]
    assert row.unit == "billions_usd", f"Expected unit='billions_usd', got {row.unit!r}"


@pytest.mark.asyncio
async def test_upsert_uses_thousands_for_payems():
    """_upsert_macro_indicator stores unit='thousands' for PAYEMS (Non-Farm Payrolls).

    RED: falls back to 'index'.
    GREEN: looks up FRED_SERIES_META → 'thousands'.
    """
    from services.gold.macro_sync import MacroSyncService

    session = _make_session()
    added_rows: list[Any] = []
    session.add.side_effect = added_rows.append

    fred = MagicMock()
    fred.fetch.return_value = [_obs("PAYEMS", value=159_000.0)]
    service = MacroSyncService(session, fred_provider=fred)

    from providers.macro_sources.fred import FRED_SERIES_META
    all_ids = tuple(FRED_SERIES_META.keys())
    result = await service.sync_fred_indicators(indicators=all_ids)

    assert result.upserted == 1
    row = added_rows[0]
    assert row.unit == "thousands", f"Expected unit='thousands', got {row.unit!r}"


@pytest.mark.asyncio
async def test_existing_dfii10_unit_unchanged():
    """Existing DFII10 (10Y TIPS) must still store unit='percent'.

    RED: N/A (this passes before the change too).
    GREEN: metadata lookup returns 'percent' for DFII10.
    """
    from services.gold.macro_sync import MacroSyncService

    session = _make_session()
    added_rows: list[Any] = []
    session.add.side_effect = added_rows.append

    fred = MagicMock()
    fred.fetch.return_value = [_obs("DFII10", value=0.85)]
    service = MacroSyncService(session, fred_provider=fred)
    result = await service.sync_fred_indicators()  # default indicators

    assert result.upserted == 1
    row = added_rows[0]
    assert row.unit == "percent", f"Expected unit='percent', got {row.unit!r}"
