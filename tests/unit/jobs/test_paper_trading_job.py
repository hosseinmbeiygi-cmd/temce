"""Unit tests for the daily PaperTradingJob.

Covers:
  - success path (signals generated → journaled → trades closed → equity)
  - database-unavailable failure
  - unexpected exceptions

Uses fakes for the async session factory, the signal orchestrator and the
paper-trading service.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.result import Result
from jobs.definitions.paper_trading_job import PaperTradingJob
from jobs.job_context import JobContext
from jobs.job_result import JobResult


def _make_context(**params: Any) -> JobContext:
    return JobContext(job_id="paper-job-1", job_name="PaperTradingJob", params=params)


class _Signal:
    """Minimal stand-in for an orchestrator signal with to_dict()."""

    def __init__(self, symbol: str, direction: str = "buy") -> None:
        self._symbol = symbol
        self._direction = direction

    def to_dict(self) -> dict[str, Any]:
        return {"symbol": self._symbol, "direction": self._direction}


class _AsyncCM:
    """Async context manager yielding a fake session."""

    def __init__(self, session: Any) -> None:
        self.session = session

    async def __aenter__(self) -> Any:
        return self.session

    async def __aexit__(self, *args: Any) -> None:
        pass


class TestPaperTradingJob:
    @pytest.mark.asyncio
    async def test_success_path(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=_AsyncCM(session))

        service = MagicMock()
        service.snapshot_signals = AsyncMock(return_value=Result.ok(2))
        service.auto_close_due_trades = AsyncMock(return_value=Result.ok(1))
        service.get_dashboard = AsyncMock(
            return_value={"total_trades": 3, "equity": 1_000_000_000.0}
        )
        service._record_equity = AsyncMock()

        orchestrator = MagicMock()
        orchestrator.generate = AsyncMock(
            return_value=MagicMock(signals=[_Signal("فولاد"), _Signal("خودرو", "sell")])
        )

        with (
            patch("core.database.async_session_factory", factory),
            patch("services.paper_trading_service.PaperTradingService", return_value=service),
            patch("services.quant_signal_orchestrator.QuantSignalOrchestrator", return_value=orchestrator),
        ):
            result = await PaperTradingJob().execute(_make_context())

        assert isinstance(result, JobResult)
        assert result.success is True
        assert result.data["signals_generated"] == 2
        assert result.data["snapshots_stored"] == 2
        assert result.data["trades_auto_closed"] == 1
        assert result.data["dashboard"]["equity"] == 1_000_000_000.0

        # Orchestrator must be called with the exact pipeline parameters the
        # job documents as "same pipeline as the API" — silent drift here
        # would change what gets journaled.
        orchestrator.generate.assert_awaited_once_with(
            market_filter="all",
            timeframe_filter="all",
            min_confidence=0.35,
            limit=100,
            use_ml=True,
            use_voting=True,
        )
        service.snapshot_signals.assert_awaited_once()
        service.auto_close_due_trades.assert_awaited_once()
        service._record_equity.assert_awaited_once()
        service.get_dashboard.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_database_unavailable(self) -> None:
        with patch("core.database.async_session_factory", None):
            result = await PaperTradingJob().execute(_make_context())

        assert result.success is False
        assert "database" in result.error.lower()

    @pytest.mark.asyncio
    async def test_orchestrator_failure_returns_failure(self) -> None:
        session = MagicMock()
        factory = MagicMock(return_value=_AsyncCM(session))
        orchestrator = MagicMock()
        orchestrator.generate = AsyncMock(side_effect=RuntimeError("signal pipeline crashed"))

        with (
            patch("core.database.async_session_factory", factory),
            patch("services.paper_trading_service.PaperTradingService", return_value=MagicMock()),
            patch("services.quant_signal_orchestrator.QuantSignalOrchestrator", return_value=orchestrator),
        ):
            result = await PaperTradingJob().execute(_make_context())

        assert result.success is False
        assert "signal pipeline crashed" in result.error

    @pytest.mark.asyncio
    async def test_snapshot_failure_is_tolerated(self) -> None:
        """A failed snapshot step must not abort the whole job."""
        session = MagicMock()
        factory = MagicMock(return_value=_AsyncCM(session))

        service = MagicMock()
        service.snapshot_signals = AsyncMock(return_value=Result.fail("journal failed"))
        service.auto_close_due_trades = AsyncMock(return_value=Result.ok(0))
        service.get_dashboard = AsyncMock(return_value={})
        service._record_equity = AsyncMock()

        orchestrator = MagicMock()
        orchestrator.generate = AsyncMock(return_value=MagicMock(signals=[_Signal("فولاد")]))

        with (
            patch("core.database.async_session_factory", factory),
            patch("services.paper_trading_service.PaperTradingService", return_value=service),
            patch("services.quant_signal_orchestrator.QuantSignalOrchestrator", return_value=orchestrator),
        ):
            result = await PaperTradingJob().execute(_make_context())

        assert result.success is True
        assert result.data["snapshots_stored"] == 0  # snapshot failure surfaced as 0
