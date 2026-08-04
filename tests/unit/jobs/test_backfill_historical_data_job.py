"""Tests for BackfillHistoricalDataJob covering all three backfill phases."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brsapi.services.sync_service import SyncReport
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from services.history_backfill_service import (
    BACKFILL_PHASES,
    BackfillHistoricalDataJob,
    _apply_phase_overrides,
)


class _AsyncContextManager:
    """Simple async context manager helper for mocking async factories."""

    def __init__(self, value: Any) -> None:
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *args: Any) -> None:
        pass


def _make_context(**params: Any) -> JobContext:
    return JobContext(job_id="test-job-1", job_name="BackfillHistoricalDataJob", params=params)


def _make_mock_session() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    return session


def _make_mock_client() -> AsyncMock:
    client = AsyncMock()
    client.stop = AsyncMock()
    return client


def _make_mock_sync_service() -> AsyncMock:
    svc = AsyncMock()
    svc.sync_history_price.return_value = SyncReport(
        endpoint="/Tsetmc/History.php", success=True, items_count=3
    )
    svc.sync_candlesticks.return_value = SyncReport(
        endpoint="/Tsetmc/Candlestick.php", success=True, items_count=4
    )
    svc.sync_shareholders.return_value = SyncReport(
        endpoint="/Tsetmc/Shareholder.php", success=True, items_count=5
    )
    return svc


@pytest.mark.asyncio
@patch("services.history_backfill_service.async_session_factory")
@patch("services.history_backfill_service.get_client")
@patch("services.history_backfill_service.BrsApiSyncService")
@patch("services.history_backfill_service.get_symbols_needing_backfill", return_value=["SYM1", "SYM2"])
@patch(
    "services.history_backfill_service.get_backfill_stats",
    return_value={
        "total_instruments": 2,
        "with_data": 0,
        "missing": 2,
        "total_rows": 0,
        "avg_rows_per_symbol": 0.0,
    },
)
async def test_backfill_historical_data_job_all_phases_success(
    _mock_get_stats: Any,
    _mock_get_symbols: Any,
    mock_service_cls: Any,
    mock_get_client: Any,
    mock_session_factory: Any,
) -> None:
    """BackfillHistoricalDataJob should run history, candlestick, and shareholder phases."""
    mock_session = _make_mock_session()
    mock_session_factory.return_value = _AsyncContextManager(mock_session)
    mock_get_client.return_value = _make_mock_client()

    mock_sync_service = _make_mock_sync_service()
    mock_service_cls.return_value = mock_sync_service

    context = _make_context()
    job = BackfillHistoricalDataJob()
    result = await job.execute(context)

    assert isinstance(result, JobResult)
    assert result.success is True
    assert result.job_name == "BackfillHistoricalDataJob"

    # All three sync methods should be called once per symbol.
    assert mock_sync_service.sync_history_price.call_count == 2
    assert mock_sync_service.sync_candlesticks.call_count == 2
    assert mock_sync_service.sync_shareholders.call_count == 2

    phases = result.data["phases"]
    assert len(phases) == 3
    assert {p["phase"] for p in phases} == {"history", "candlestick", "shareholder"}
    for phase in phases:
        assert phase["status"] == "completed"
        assert phase["total_symbols_processed"] == 2
        assert phase["succeeded"] == 2
        assert phase["failed"] == 0

    # The session should be committed after each phase.
    assert mock_session.commit.await_count == 3


@pytest.mark.asyncio
@patch("services.history_backfill_service.async_session_factory")
@patch("services.history_backfill_service.get_client")
@patch("services.history_backfill_service.BrsApiSyncService")
@patch("services.history_backfill_service.get_symbols_needing_backfill", return_value=[])
@patch(
    "services.history_backfill_service.get_backfill_stats",
    return_value={
        "total_instruments": 2,
        "with_data": 2,
        "missing": 0,
        "total_rows": 100,
        "avg_rows_per_symbol": 50.0,
    },
)
async def test_backfill_historical_data_job_empty_phases(
    _mock_get_stats: Any,
    _mock_get_symbols: Any,
    mock_service_cls: Any,
    mock_get_client: Any,
    mock_session_factory: Any,
) -> None:
    """BackfillHistoricalDataJob should skip phases when no symbols need backfill."""
    mock_session = _make_mock_session()
    mock_session_factory.return_value = _AsyncContextManager(mock_session)
    mock_get_client.return_value = _make_mock_client()

    mock_sync_service = _make_mock_sync_service()
    mock_service_cls.return_value = mock_sync_service

    context = _make_context()
    job = BackfillHistoricalDataJob()
    result = await job.execute(context)

    assert result.success is True
    phases = result.data["phases"]
    assert len(phases) == 3
    for phase in phases:
        assert phase["status"] == "skipped"

    # No sync service methods should be called when no symbols need backfill.
    assert mock_sync_service.sync_history_price.call_count == 0
    assert mock_sync_service.sync_candlesticks.call_count == 0
    assert mock_sync_service.sync_shareholders.call_count == 0


@pytest.mark.asyncio
@patch("services.history_backfill_service.async_session_factory")
@patch("services.history_backfill_service.get_client")
@patch("services.history_backfill_service.BrsApiSyncService")
@patch("services.history_backfill_service.get_symbols_needing_backfill", return_value=["SYM1", "SYM2"])
@patch(
    "services.history_backfill_service.get_backfill_stats",
    return_value={
        "total_instruments": 2,
        "with_data": 0,
        "missing": 2,
        "total_rows": 0,
        "avg_rows_per_symbol": 0.0,
    },
)
async def test_backfill_historical_data_job_partial_failure(
    _mock_get_stats: Any,
    _mock_get_symbols: Any,
    mock_service_cls: Any,
    mock_get_client: Any,
    mock_session_factory: Any,
) -> None:
    """BackfillHistoricalDataJob should report failed symbols across all three phases but still return success."""
    mock_session = _make_mock_session()
    mock_session_factory.return_value = _AsyncContextManager(mock_session)
    mock_get_client.return_value = _make_mock_client()

    mock_sync_service = _make_mock_sync_service()
    # First symbol fails on history; second symbol fails on candlestick.
    mock_sync_service.sync_history_price.side_effect = [
        SyncReport(endpoint="/Tsetmc/History.php", success=False, error="network"),
        SyncReport(endpoint="/Tsetmc/History.php", success=True, items_count=3),
    ]
    mock_sync_service.sync_candlesticks.side_effect = [
        SyncReport(endpoint="/Tsetmc/Candlestick.php", success=True, items_count=4),
        SyncReport(endpoint="/Tsetmc/Candlestick.php", success=False, error="timeout"),
    ]
    mock_sync_service.sync_shareholders.side_effect = [
        SyncReport(endpoint="/Tsetmc/Shareholder.php", success=False, error="missing"),
        SyncReport(endpoint="/Tsetmc/Shareholder.php", success=True, items_count=5),
    ]
    mock_service_cls.return_value = mock_sync_service

    context = _make_context()
    job = BackfillHistoricalDataJob()
    result = await job.execute(context)

    assert result.success is True
    history_phase = next(p for p in result.data["phases"] if p["phase"] == "history")
    candlestick_phase = next(p for p in result.data["phases"] if p["phase"] == "candlestick")
    shareholder_phase = next(p for p in result.data["phases"] if p["phase"] == "shareholder")
    assert history_phase["succeeded"] == 1
    assert history_phase["failed"] == 1
    assert candlestick_phase["succeeded"] == 1
    assert candlestick_phase["failed"] == 1
    assert shareholder_phase["succeeded"] == 1
    assert shareholder_phase["failed"] == 1
    assert "network" in history_phase["errors"]
    assert "timeout" in candlestick_phase["errors"]
    assert "missing" in shareholder_phase["errors"]


@pytest.mark.asyncio
@patch("services.history_backfill_service.async_session_factory")
@patch("services.history_backfill_service.get_client")
@patch("services.history_backfill_service.BrsApiSyncService")
@patch("services.history_backfill_service.get_symbols_needing_backfill", return_value=["SYM1", "SYM2", "SYM3"])
@patch(
    "services.history_backfill_service.get_backfill_stats",
    return_value={
        "total_instruments": 3,
        "with_data": 0,
        "missing": 3,
        "total_rows": 0,
        "avg_rows_per_symbol": 0.0,
    },
)
async def test_backfill_historical_data_job_context_params(
    _mock_get_stats: Any,
    _mock_get_symbols: Any,
    mock_service_cls: Any,
    mock_get_client: Any,
    mock_session_factory: Any,
) -> None:
    """BackfillHistoricalDataJob should pass data_types and max_symbols from context."""
    mock_session = _make_mock_session()
    mock_session_factory.return_value = _AsyncContextManager(mock_session)
    mock_get_client.return_value = _make_mock_client()

    mock_sync_service = _make_mock_sync_service()
    mock_service_cls.return_value = mock_sync_service

    context = _make_context(data_types=["history"], max_symbols=2)
    job = BackfillHistoricalDataJob()
    result = await job.execute(context)

    assert result.success is True
    phases = result.data["phases"]
    assert len(phases) == 1
    assert phases[0]["phase"] == "history"
    # max_symbols=2 should limit processing to 2 symbols.
    assert phases[0]["total_symbols_processed"] == 2

    # Only history method should be called for exactly 2 symbols.
    assert mock_sync_service.sync_history_price.call_count == 2
    assert mock_sync_service.sync_candlesticks.call_count == 0
    assert mock_sync_service.sync_shareholders.call_count == 0


@pytest.mark.asyncio
async def test_backfill_historical_data_job_invalid_override_types() -> None:
    """BackfillHistoricalDataJob should fail fast when batch_sizes or delay_seconds are not dicts."""
    job = BackfillHistoricalDataJob()

    context = _make_context(batch_sizes=[1, 2, 3])
    result = await job.execute(context)
    assert result.success is False
    assert "batch_sizes must be a dict" in result.error

    context = _make_context(delay_seconds=5.0)
    result = await job.execute(context)
    assert result.success is False
    assert "delay_seconds must be a dict" in result.error


@pytest.mark.asyncio
async def test_backfill_historical_data_job_invalid_data_types_and_max_symbols() -> None:
    """BackfillHistoricalDataJob should fail fast with invalid data_types or max_symbols."""
    job = BackfillHistoricalDataJob()

    context = _make_context(data_types="history")
    result = await job.execute(context)
    assert result.success is False
    assert "data_types must be a list" in result.error

    context = _make_context(max_symbols={"history": "one"})
    result = await job.execute(context)
    assert result.success is False
    assert "max_symbols dict values must be integers" in result.error


@pytest.mark.asyncio
async def test_backfill_historical_data_job_execute_backfill_error() -> None:
    """BackfillHistoricalDataJob should return failure when execute_backfill reports an error."""
    with patch(
        "services.history_backfill_service.execute_backfill",
        return_value={"error": "database not initialized"},
    ):
        context = _make_context()
        job = BackfillHistoricalDataJob()
        result = await job.execute(context)

    assert result.success is False
    assert result.error == "database not initialized"


def test_apply_phase_overrides_applies_batch_size_and_delay() -> None:
    """_apply_phase_overrides should override batch_size and delay_seconds while preserving other fields."""
    phase = BACKFILL_PHASES["history"]
    overridden = _apply_phase_overrides(phase, {"batch_size": 99, "delay_seconds": 0.5})
    assert overridden.batch_size == 99
    assert overridden.delay_seconds == 0.5
    assert overridden.min_count == phase.min_count
    assert overridden.table_name == phase.table_name


def test_apply_phase_overrides_rejects_non_numeric() -> None:
    """_apply_phase_overrides should raise ValueError for non-numeric overrides."""
    phase = BACKFILL_PHASES["history"]
    with pytest.raises(ValueError):
        _apply_phase_overrides(phase, {"batch_size": "fast"})


@pytest.mark.asyncio
@patch("services.history_backfill_service.asyncio.sleep")
@patch("services.history_backfill_service.async_session_factory")
@patch("services.history_backfill_service.get_client")
@patch("services.history_backfill_service.BrsApiSyncService")
@patch("services.history_backfill_service.get_symbols_needing_backfill", return_value=["SYM1", "SYM2"])
@patch(
    "services.history_backfill_service.get_backfill_stats",
    return_value={
        "total_instruments": 2,
        "with_data": 0,
        "missing": 2,
        "total_rows": 0,
        "avg_rows_per_symbol": 0.0,
    },
)
async def test_backfill_historical_data_job_phase_overrides(
    _mock_get_stats: Any,
    _mock_get_symbols: Any,
    mock_service_cls: Any,
    mock_get_client: Any,
    mock_session_factory: Any,
    mock_sleep: Any,
) -> None:
    """BackfillHistoricalDataJob should apply per-phase max_symbols, batch_size, and delay_seconds."""
    mock_session = _make_mock_session()
    mock_session_factory.return_value = _AsyncContextManager(mock_session)
    mock_get_client.return_value = _make_mock_client()

    mock_sync_service = _make_mock_sync_service()
    mock_service_cls.return_value = mock_sync_service

    context = _make_context(
        data_types=["history", "candlestick"],
        max_symbols={"history": 2, "candlestick": 2},
        batch_sizes={"history": 1},
        delay_seconds={"history": 0.5},
    )
    job = BackfillHistoricalDataJob()
    result = await job.execute(context)

    assert result.success is True
    phases = result.data["phases"]
    assert len(phases) == 2

    history_phase = next(p for p in phases if p["phase"] == "history")
    candlestick_phase = next(p for p in phases if p["phase"] == "candlestick")

    # Per-phase max_symbols should limit history and candlestick to 2 symbols.
    assert history_phase["total_symbols_processed"] == 2
    assert candlestick_phase["total_symbols_processed"] == 2

    # The overridden batch_size for history means 1 symbol per batch.
    assert mock_sync_service.sync_history_price.call_count == 2
    assert mock_sync_service.sync_candlesticks.call_count == 2

    # Two history batches with a per-batch delay of 0.5s between them.
    mock_sleep.assert_called_once_with(0.5)


@pytest.mark.asyncio
async def test_backfill_historical_data_job_unexpected_exception() -> None:
    """BackfillHistoricalDataJob should return failure when execute_backfill raises unexpectedly."""
    with patch(
        "services.history_backfill_service.execute_backfill",
        side_effect=RuntimeError("unexpected boom"),
    ):
        context = _make_context()
        job = BackfillHistoricalDataJob()
        result = await job.execute(context)

    assert result.success is False
    assert "unexpected boom" in result.error
