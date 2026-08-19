"""Unit tests for the FundsSyncJob.

Covers:
  - success path with a mocked FundSyncService report
  - session failure (no DB session available)
  - unexpected exceptions inside the job
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.definitions.fund_jobs import FundsSyncJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.fund_sync_service import SyncReport


def _make_context(**params: Any) -> JobContext:
    return JobContext(job_id="funds-job-1", job_name="FundsSyncJob", params=params)


def _make_get_session(session: MagicMock):
    """get_session is an async-generator function — the replacement must be
    an async-generator function too so ``async for`` works."""
    async def _gen():
        yield session

    return _gen


def _make_report(total: int = 80, success: int = 75, failed: int = 5) -> SyncReport:
    return SyncReport(
        total=total,
        success=success,
        failed=failed,
        errors=[{"symbol": "غایب", "error": "not found"}],
        duration_ms=1234.5,
    )


class TestFundsSyncJob:
    @pytest.mark.asyncio
    async def test_success_report_data(self) -> None:
        session = MagicMock()
        sync_cls = MagicMock()
        sync = sync_cls.return_value
        sync.sync_all_funds = AsyncMock(return_value=_make_report())

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.fund_sync_service.FundSyncService", sync_cls),
            patch("services.fund_service.FundService"),
            patch("brsapi.services.query_service.BrsApiQueryService"),
        ):
            result = await FundsSyncJob().execute(_make_context())

        assert isinstance(result, JobResult)
        assert result.success is True
        assert result.data["total"] == 80
        assert result.data["success_count"] == 75
        assert result.data["failed_count"] == 5
        assert result.data["errors"][0]["symbol"] == "غایب"
        assert result.data["duration_ms"] == 1234.5
        # Known fund symbols are passed to the sync service — this is the
        # job's core contract, so verify the exact argument.
        from services.fund_sync_service import KNOWN_FUND_SYMBOLS

        sync.sync_all_funds.assert_awaited_once_with(symbols=KNOWN_FUND_SYMBOLS)

    @pytest.mark.asyncio
    async def test_no_session_returns_failure(self) -> None:
        async def _empty():
            if False:
                yield None

        with patch("core.database.get_session", _empty):
            result = await FundsSyncJob().execute(_make_context())

        assert result.success is False
        assert "session" in result.error.lower()

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        session = MagicMock()
        sync_cls = MagicMock()
        sync = sync_cls.return_value
        sync.sync_all_funds = AsyncMock(side_effect=RuntimeError("timeout"))

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.fund_sync_service.FundSyncService", sync_cls),
            patch("services.fund_service.FundService"),
            patch("brsapi.services.query_service.BrsApiQueryService"),
        ):
            result = await FundsSyncJob().execute(_make_context())

        assert result.success is False
        assert "timeout" in result.error
