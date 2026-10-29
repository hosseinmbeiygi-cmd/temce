"""Source-read failures must not be reported as ``success=True`` empty data.

Two endpoints returned ``success=True`` with an empty payload from their
``except`` block, so a broken DB / provider read looked exactly like a valid
"nothing here yet":

  * ``GET /analysis/correlations`` (snapshot fetch failed)
  * ``GET /codal/{code}/financials`` (statement query failed)

Both must now answer ``success=False`` so callers (and the frontend
``apiGet`` envelope) can distinguish source failure from success-empty.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class _FailingBrsapi:
    async def get_latest_snapshots(self, **_kwargs):
        raise RuntimeError("snapshot source down")


class _FailingSession:
    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("codal table read failed")


@pytest.mark.asyncio
async def test_analysis_correlations_source_error_is_success_false() -> None:
    from apps.api.endpoints import analysis as analysis_mod

    response = await analysis_mod.analysis_correlations(brsapi=_FailingBrsapi())

    assert response.success is False
    assert response.data["categories"] == []
    assert response.data["source"] == "unavailable"


@pytest.mark.asyncio
async def test_codal_financials_source_error_is_success_false() -> None:
    from apps.api.endpoints import codal as codal_mod

    response = await codal_mod.financial_reports(code="TEST", session=_FailingSession())

    assert response.success is False
    assert response.data["quarters"] == []
