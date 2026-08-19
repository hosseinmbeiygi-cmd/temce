"""Unit tests for the master sync service.

Covers:
  - ``PhaseReport`` / ``MasterReport`` dataclass aggregations
  - ``_add_operation`` failure propagation
  - ``_get_all_symbols`` query handling
  - ``_phase_1_bulk_market`` orchestration (list / single report results)
  - ``_phase_5_codal`` announcement + download steps
  - ``run_all`` phase selection + catastrophic failure capture

Uses fake sync services and sessions — no network or DB.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brsapi.services.sync_service import SyncReport
from services.sync_master_service import MasterReport, MasterSyncService, PhaseReport

# ── Helpers ───────────────────────────────────────────────────────────────


def _make_report(success: bool = True, items: int = 5, error: str | None = None) -> SyncReport:
    return SyncReport(
        endpoint="/Tsetmc/Symbol.php",
        success=success,
        items_count=items,
        error=error,
        duration_ms=12.5,
    )


def _make_sync_svc() -> MagicMock:
    """Fake BrsApiSyncService with every sync_* method returning a report."""
    svc = MagicMock()
    for name in (
        "sync_all_symbols",
        "sync_index",
        "sync_options",
        "sync_ime_futures",
        "sync_ime_options",
        "sync_ime_certificates",
        "sync_ime_funds",
        "sync_commodities",
        "sync_crypto",
        "sync_gold_currency",
        "sync_symbol_detail",
        "sync_candlesticks",
        "sync_history_price",
        "sync_transactions",
        "sync_shareholders",
        "sync_codal",
    ):
        setattr(svc, name, AsyncMock(return_value=_make_report()))
    return svc


def _make_session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    return session


def _make_service(svc: MagicMock | None = None, session: MagicMock | None = None) -> MasterSyncService:
    service = MasterSyncService(
        client=MagicMock(),
        max_symbols_per_phase=2,
        transaction_days_back=2,
    )
    service._sync_svc = svc or _make_sync_svc()
    return service


# ── Dataclasses ───────────────────────────────────────────────────────────


class TestPhaseReport:
    def test_total_items_sums_operations(self) -> None:
        phase = PhaseReport(phase_name="P1", success=True)
        phase.operations = [
            {"items": 3},
            {"items": 4},
            {"items": 0},
        ]
        assert phase.total_items == 7


class TestMasterReport:
    def test_aggregations(self) -> None:
        report = MasterReport(started_at=0.0, finished_at=2.0)
        report.phases = [
            PhaseReport(phase_name="A", success=True, operations=[{"items": 3}]),
            PhaseReport(phase_name="B", success=False, operations=[{"items": 5}], error="boom"),
        ]
        assert report.total_duration_ms == 2000.0
        assert report.total_items == 8
        assert report.all_successful is False
        assert report.errors == []

    def test_print_summary_does_not_raise(self, capsys) -> None:
        report = MasterReport()
        report.phases = [PhaseReport(phase_name="A", success=True, operations=[{"items": 2}])]
        report.print_summary()
        out = capsys.readouterr().out
        assert "MASTER SYNC REPORT" in out


# ── _add_operation ────────────────────────────────────────────────────────


class TestAddOperation:
    @pytest.mark.asyncio
    async def test_failure_marks_phase_failed(self) -> None:
        service = _make_service()
        phase = PhaseReport(phase_name="P", success=True)

        await service._add_operation(phase, "op", False, error="network error")

        assert phase.success is False
        assert phase.operations[0]["success"] is False
        assert phase.operations[0]["error"] == "network error"

    @pytest.mark.asyncio
    async def test_success_keeps_phase_success(self) -> None:
        service = _make_service()
        phase = PhaseReport(phase_name="P", success=True)

        await service._add_operation(phase, "op", True, items=9)

        assert phase.success is True
        assert phase.operations[0]["items"] == 9


# ── _get_all_symbols ──────────────────────────────────────────────────────


class TestGetAllSymbols:
    @pytest.mark.asyncio
    async def test_returns_symbols_from_query(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock(return_value=[("فولاد",), ("خودرو",)])
        service = MasterSyncService()

        symbols = await service._get_all_symbols(session)

        assert symbols == ["فولاد", "خودرو"]


# ── _phase_1_bulk_market ──────────────────────────────────────────────────


class TestPhase1BulkMarket:
    @pytest.mark.asyncio
    async def test_all_bulk_ops_success(self) -> None:
        session = _make_session()
        svc = _make_sync_svc()
        service = _make_service(svc=svc, session=session)

        with patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()):
            phase = await service._phase_1_bulk_market(session)

        assert phase.success is True
        assert phase.total_items == 11 * 5  # 11 bulk ops × 5 items
        assert len(phase.operations) == 11
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_single_op_failure_marks_phase_failed(self) -> None:
        session = _make_session()
        svc = _make_sync_svc()
        # The Options sync fails.
        svc.sync_options = AsyncMock(return_value=_make_report(success=False, error="quota"))
        service = _make_service(svc=svc, session=session)

        with patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()):
            phase = await service._phase_1_bulk_market(session)

        assert phase.success is False
        names = [op["name"] for op in phase.operations]
        assert "Options (TSETMC)" in names
        options_op = next(op for op in phase.operations if op["name"] == "Options (TSETMC)")
        assert options_op["success"] is False
        assert options_op["error"] == "quota"

    @pytest.mark.asyncio
    async def test_exception_in_op_is_caught(self) -> None:
        session = _make_session()
        svc = _make_sync_svc()
        svc.sync_crypto = AsyncMock(side_effect=RuntimeError("boom"))
        service = _make_service(svc=svc, session=session)

        with patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()):
            phase = await service._phase_1_bulk_market(session)

        assert phase.success is False
        crypto_op = next(op for op in phase.operations if op["name"] == "Crypto")
        assert crypto_op["success"] is False
        assert "boom" in crypto_op["error"]

    @pytest.mark.asyncio
    async def test_list_result_records_each_sub_report(self) -> None:
        """When an op returns a list of reports, each sub-report becomes an operation."""
        session = _make_session()
        svc = _make_sync_svc()
        # AllSymbols returns two per-endpoint reports.
        svc.sync_all_symbols = AsyncMock(
            return_value=[
                _make_report(success=True, items=3),
                _make_report(success=False, items=0, error="partial"),
            ]
        )
        service = _make_service(svc=svc, session=session)

        with patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()):
            phase = await service._phase_1_bulk_market(session)

        # 10 other ops + 2 sub-reports from AllSymbols.
        assert len(phase.operations) == 12
        sub_names = [op["name"] for op in phase.operations if op["name"].startswith("AllSymbols/" )]
        assert len(sub_names) == 2
        assert phase.success is False  # the failing sub-report propagates


# ── _phase_2_symbol_details ───────────────────────────────────────────────


class TestPhase2SymbolDetails:
    @pytest.mark.asyncio
    async def test_processes_symbols_and_commits(self) -> None:
        session = _make_session()
        svc = _make_sync_svc()
        service = _make_service(svc=svc, session=session)
        # max_symbols_per_phase=2 → two symbols, three ops each.
        session.execute = AsyncMock(return_value=[("فولاد",), ("خودرو",)])

        with patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()):
            phase = await service._phase_2_symbol_details(session)

        assert phase.success is True
        assert len(phase.operations) == 6  # 2 symbols × 3 ops
        assert phase.total_items == 30  # 6 × 5 items
        session.commit.assert_awaited()


# ── _phase_5_codal ────────────────────────────────────────────────────────


class TestPhase5Codal:
    @pytest.mark.asyncio
    async def test_announcement_and_download_steps(self) -> None:
        session = _make_session()
        svc = _make_sync_svc()
        service = _make_service(svc=svc, session=session)

        dl_service = MagicMock()
        dl_service.download_and_import_all = AsyncMock(
            return_value=MagicMock(parsed=12, errors=[])
        )
        dl_service.close = AsyncMock()

        with (
            patch("services.codal_download_service.CodalDownloadService", return_value=dl_service),
            patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()),
        ):
            phase = await service._phase_5_codal(session)

        assert phase.success is True
        assert phase.total_items == 5 + 12  # announcements + parsed files
        dl_service.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_download_step_failure_is_caught(self) -> None:
        session = _make_session()
        svc = _make_sync_svc()
        service = _make_service(svc=svc, session=session)

        dl_service = MagicMock()
        dl_service.download_and_import_all = AsyncMock(side_effect=RuntimeError("disk full"))
        dl_service.close = AsyncMock()

        with (
            patch("services.codal_download_service.CodalDownloadService", return_value=dl_service),
            patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()),
        ):
            phase = await service._phase_5_codal(session)

        assert phase.success is False
        dl_op = next(op for op in phase.operations if op["name"] == "Codal Download & Parse")
        assert dl_op["success"] is False
        assert "disk full" in dl_op["error"]
        dl_service.close.assert_awaited_once()


# ── run_all ───────────────────────────────────────────────────────────────


class TestRunAll:
    @pytest.mark.asyncio
    async def test_runs_selected_phase_only(self) -> None:
        service = _make_service()
        service._phase_1_bulk_market = AsyncMock(
            return_value=PhaseReport(phase_name="Phase 1 — Bulk Market", success=True)
        )

        with patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()):
            report = await service.run_all(session=MagicMock(), phases=[1])

        assert isinstance(report, MasterReport)
        assert len(report.phases) == 1
        assert report.phases[0].phase_name == "Phase 1 — Bulk Market"
        assert report.total_duration_ms >= 0.0

    @pytest.mark.asyncio
    async def test_unknown_phase_is_skipped(self) -> None:
        service = _make_service()

        with patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()):
            report = await service.run_all(session=MagicMock(), phases=[99])

        assert report.phases == []

    @pytest.mark.asyncio
    async def test_catastrophic_phase_failure_is_captured(self) -> None:
        service = _make_service()
        service._phase_1_bulk_market = AsyncMock(side_effect=RuntimeError("fatal"))

        with patch("services.sync_master_service.asyncio.sleep", new=AsyncMock()):
            report = await service.run_all(session=MagicMock(), phases=[1])

        assert len(report.phases) == 1
        assert report.phases[0].success is False
        assert "Fatal" in (report.phases[0].error or "")
        assert report.errors == ["Phase 1: fatal"]
