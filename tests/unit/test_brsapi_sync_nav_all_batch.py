"""Unit tests for the ``BrsApiSyncService.sync_nav_all`` batch breakdown.

The batch report used to expose only ``success`` / ``items_count`` /
``failed_symbols``, so a run where every fetch "succeeded" but wrote zero
rows (BrsApi still serving yesterday's NAV) looked identical to a healthy
sync. These tests lock in the ``skipped_symbols`` / ``no_data_symbols``
breakdown using a mocked session and a mocked per-symbol ``sync_nav``
(no database, no network).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is importable when pytest is invoked from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from brsapi.services.sync_service import (
    BrsApiSyncService,
    SyncReport,
    canonical_nav_symbol,
)


def _nav_report(**overrides: object) -> SyncReport:
    defaults: dict[str, object] = {
        "endpoint": "/Tsetmc/Nav.php",
        "success": True,
        "items_count": 0,
        "duration_ms": 1.0,
        "error": None,
        "skipped": False,
    }
    defaults.update(overrides)
    return SyncReport(**defaults)  # type: ignore[arg-type]


def _fake_session(done_symbols: tuple[str, ...] = ()) -> MagicMock:
    """Session whose NAV fast-path query reports ``done_symbols`` as stored."""
    session = MagicMock()
    session.execute = AsyncMock(return_value=[(s,) for s in done_symbols])
    return session


@pytest.mark.asyncio
async def test_batch_separates_stored_no_data_skipped_and_failed() -> None:
    """Each "nothing was written" outcome lands in its own bucket."""
    session = _fake_session(done_symbols=("A",))
    reports = {
        "B": _nav_report(items_count=3),  # stored
        "C": _nav_report(items_count=0),  # fetched OK, source had nothing new
        "D": _nav_report(success=False, error="HTTP 502"),  # real failure
    }

    async def fake_sync_nav(_session: object, symbol: str) -> SyncReport:
        return reports[symbol]

    with patch.object(BrsApiSyncService, "sync_nav", AsyncMock(side_effect=fake_sync_nav)):
        svc = BrsApiSyncService(client=MagicMock())
        report = await svc.sync_nav_all(
            session, symbols=["A", "B", "C", "D"], sleep_seconds=0
        )

    assert report.items_count == 3
    assert report.success is False
    assert report.failed_symbols == ["D"]
    assert report.skipped_symbols == ["A"]
    assert report.no_data_symbols == ["C"]
    assert "D" in (report.error or "")


@pytest.mark.asyncio
async def test_all_symbols_have_today_nav_marks_skipped() -> None:
    """A fully cached run is ``skipped`` and never calls ``sync_nav``."""
    session = _fake_session(done_symbols=("A", "B"))
    fake_sync_nav = AsyncMock()

    with patch.object(BrsApiSyncService, "sync_nav", fake_sync_nav):
        svc = BrsApiSyncService(client=MagicMock())
        report = await svc.sync_nav_all(session, symbols=["A", "B"], sleep_seconds=0)

    assert report.success is True
    assert report.skipped is True
    assert report.items_count == 0
    assert report.skipped_symbols == ["A", "B"]
    assert report.no_data_symbols == []
    fake_sync_nav.assert_not_awaited()


@pytest.mark.asyncio
async def test_per_symbol_skip_is_not_counted_as_no_data() -> None:
    """A per-symbol skip (fast-path query failed) is not "no data"."""
    session = MagicMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))

    async def fake_sync_nav(_session: object, symbol: str) -> SyncReport:
        return _nav_report(skipped=True)

    with patch.object(BrsApiSyncService, "sync_nav", AsyncMock(side_effect=fake_sync_nav)):
        svc = BrsApiSyncService(client=MagicMock())
        report = await svc.sync_nav_all(session, symbols=["A"], sleep_seconds=0)

    assert report.success is True
    assert report.skipped_symbols == ["A"]
    assert report.no_data_symbols == []


def test_canonical_nav_symbol_folds_known_duplicate_twins() -> None:
    """TSETMC name-collision twins (``ابتکار2``) map onto their base symbol."""
    known = {"ابتکار", "آتیه ملت", "پالایش", "اعتماد"}

    assert canonical_nav_symbol("ابتکار2", known) == "ابتکار"
    assert canonical_nav_symbol("آتیه ملت4", known) == "آتیه ملت"
    assert canonical_nav_symbol("پالایش4", known) == "پالایش"
    # A plain symbol is returned untouched, even when it ends with a digit
    # that happens to be part of the name.
    assert canonical_nav_symbol("ابتکار", known) == "ابتکار"
    # No base in the batch -> the symbol is never invented/resolved.
    assert canonical_nav_symbol("آتی1", known) == "آتی1"
    assert canonical_nav_symbol("", known) == ""


@pytest.mark.asyncio
async def test_batch_folds_duplicate_twins_before_fetching() -> None:
    """The batch fetches each fund once and reports the folded twins."""
    session = _fake_session()
    fetched: list[str] = []

    async def fake_sync_nav(_session: object, symbol: str) -> SyncReport:
        fetched.append(symbol)
        return _nav_report(items_count=1)

    with patch.object(BrsApiSyncService, "sync_nav", AsyncMock(side_effect=fake_sync_nav)):
        svc = BrsApiSyncService(client=MagicMock())
        report = await svc.sync_nav_all(
            session,
            symbols=["ابتکار2", "ابتکار", "آتیه ملت4", "آتیه ملت", "آتی1"],
            sleep_seconds=0,
        )

    assert fetched == ["ابتکار", "آتیه ملت", "آتی1"]
    assert report.normalized_symbols == ["ابتکار2", "آتیه ملت4"]
    assert report.failed_symbols == []
    assert report.items_count == 3
