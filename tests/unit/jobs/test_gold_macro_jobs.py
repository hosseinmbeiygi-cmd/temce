"""Unit tests for the gold macro ingestion jobs.

Covers:
  - ``GoldMacroSyncJob`` self-skips when ``FRED_API_KEY`` is not configured
  - each job wires the matching ``MacroSyncService`` method
  - provider factories are the injection points (no network in tests)
  - missing DB session and unexpected exceptions degrade to a failed result
  - the three jobs are registered and scheduled
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs import definitions as job_definitions
from jobs.definitions.gold_macro_jobs import (
    FRED_API_KEY_ENV,
    GoldCftcCotSyncJob,
    GoldEconomicCalendarSyncJob,
    GoldMacroSyncJob,
    GoldTokenizedGoldSyncJob,
)
from jobs.job_context import JobContext
from jobs.job_result import JobResult
from jobs.registry import job_registry
from services.gold.macro_sync import SyncResult


def _make_context(job_name: str = "GoldMacroSyncJob") -> JobContext:
    return JobContext(job_id="macro-job-1", job_name=job_name, params={})


def _make_get_session(session: MagicMock):
    """``get_session`` is an async-generator function — the replacement must be
    an async-generator function too so ``async for`` works."""

    async def _gen():
        yield session

    return _gen


def _make_sync_result(**kwargs: Any) -> SyncResult:
    defaults: dict[str, Any] = {
        "job_type": "fred_macro_indicators",
        "ok": True,
        "upserted": 2,
        "skipped": 0,
        "errors": [],
        "duration_ms": 12.5,
    }
    defaults.update(kwargs)
    return SyncResult(**defaults)


def _patched_service(sync_result: SyncResult):
    """Patch ``MacroSyncService`` so the job talks to a stub, never a provider."""
    service_cls = MagicMock()
    service = service_cls.return_value
    service.sync_fred_indicators = AsyncMock(return_value=sync_result)
    service.sync_cftc_cot_gold = AsyncMock(return_value=sync_result)
    service.sync_economic_calendar = AsyncMock(return_value=sync_result)
    service.sync_tokenized_gold_premium = AsyncMock(return_value=sync_result)
    return service_cls, service


class TestGoldMacroSyncJob:
    @pytest.mark.asyncio
    async def test_skips_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(FRED_API_KEY_ENV, raising=False)
        session = MagicMock()
        service_cls, service = _patched_service(_make_sync_result())

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
        ):
            result = await GoldMacroSyncJob().execute(_make_context())

        assert isinstance(result, JobResult)
        assert result.success is True
        assert result.data["skipped"] is True
        assert FRED_API_KEY_ENV in result.data["reason"]
        # The sync service must not be built at all when the key is missing.
        service_cls.assert_not_called()
        service.sync_fred_indicators.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_syncs_when_api_key_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(FRED_API_KEY_ENV, "test-key")
        session = MagicMock()
        service_cls, service = _patched_service(_make_sync_result())
        fred_provider = MagicMock()

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
            patch(
                "jobs.definitions.gold_macro_jobs._build_fred_provider",
                return_value=fred_provider,
            ),
        ):
            result = await GoldMacroSyncJob().execute(_make_context())

        assert result.success is True
        assert result.data["upserted"] == 2
        assert result.data["job_type"] == "fred_macro_indicators"
        service.sync_fred_indicators.assert_awaited_once()
        # The session and the provider must both reach the sync service.
        _, kwargs = service_cls.call_args
        assert kwargs["fred_provider"] is fred_provider

    @pytest.mark.asyncio
    async def test_no_session_returns_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(FRED_API_KEY_ENV, "test-key")
        service_cls, _ = _patched_service(_make_sync_result())

        async def _empty():
            if False:
                yield None

        with (
            patch("core.database.get_session", _empty),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
        ):
            result = await GoldMacroSyncJob().execute(_make_context())

        assert result.success is False
        assert "session" in result.error.lower()

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(FRED_API_KEY_ENV, "test-key")
        session = MagicMock()
        service_cls = MagicMock()
        service = service_cls.return_value
        service.sync_fred_indicators = AsyncMock(side_effect=RuntimeError("timeout"))

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
        ):
            result = await GoldMacroSyncJob().execute(_make_context())

        assert result.success is False
        assert "timeout" in result.error

    @pytest.mark.asyncio
    async def test_failed_sync_result_maps_to_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(FRED_API_KEY_ENV, "test-key")
        session = MagicMock()
        service_cls, _ = _patched_service(
            _make_sync_result(ok=False, upserted=0, errors=["FRED HTTP 500"])
        )

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
        ):
            result = await GoldMacroSyncJob().execute(_make_context())

        assert result.success is False
        assert "FRED HTTP 500" in result.error
        # The failure still carries the sync counters for observability.
        assert result.data["errors"] == ["FRED HTTP 500"]


class TestGoldCftcCotSyncJob:
    @pytest.mark.asyncio
    async def test_calls_cftc_sync(self) -> None:
        session = MagicMock()
        service_cls, service = _patched_service(
            _make_sync_result(job_type="cftc_cot_gold", upserted=52)
        )
        cftc_provider = MagicMock()

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
            patch(
                "jobs.definitions.gold_macro_jobs._build_cftc_provider",
                return_value=cftc_provider,
            ),
        ):
            result = await GoldCftcCotSyncJob().execute(
                _make_context("GoldCftcCotSyncJob")
            )

        assert result.success is True
        assert result.data["upserted"] == 52
        service.sync_cftc_cot_gold.assert_awaited_once()
        _, kwargs = service_cls.call_args
        assert kwargs["cftc_provider"] is cftc_provider

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        session = MagicMock()
        service_cls = MagicMock()
        service = service_cls.return_value
        service.sync_cftc_cot_gold = AsyncMock(side_effect=RuntimeError("cftc down"))

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
        ):
            result = await GoldCftcCotSyncJob().execute(
                _make_context("GoldCftcCotSyncJob")
            )

        assert result.success is False
        assert "cftc down" in result.error


class TestGoldEconomicCalendarSyncJob:
    @pytest.mark.asyncio
    async def test_calls_calendar_sync(self) -> None:
        session = MagicMock()
        service_cls, service = _patched_service(
            _make_sync_result(job_type="economic_calendar", upserted=6)
        )
        calendar_provider = MagicMock()

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
            patch(
                "jobs.definitions.gold_macro_jobs._build_calendar_provider",
                return_value=calendar_provider,
            ),
        ):
            result = await GoldEconomicCalendarSyncJob().execute(
                _make_context("GoldEconomicCalendarSyncJob")
            )

        assert result.success is True
        assert result.data["upserted"] == 6
        service.sync_economic_calendar.assert_awaited_once()
        _, kwargs = service_cls.call_args
        assert kwargs["calendar_provider"] is calendar_provider


class TestGoldTokenizedGoldSyncJob:
    @pytest.mark.asyncio
    async def test_calls_tokenized_gold_sync(self) -> None:
        session = MagicMock()
        service_cls, service = _patched_service(
            _make_sync_result(job_type="tokenized_gold_premium", upserted=2)
        )
        tokenized_provider = MagicMock()
        spot_provider = MagicMock()

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
            patch(
                "jobs.definitions.gold_macro_jobs._build_tokenized_gold_provider",
                return_value=tokenized_provider,
            ),
            patch(
                "jobs.definitions.gold_macro_jobs._build_gold_spot_provider",
                return_value=spot_provider,
            ),
        ):
            result = await GoldTokenizedGoldSyncJob().execute(
                _make_context("GoldTokenizedGoldSyncJob")
            )

        assert result.success is True
        assert result.data["upserted"] == 2
        service.sync_tokenized_gold_premium.assert_awaited_once()
        _, kwargs = service_cls.call_args
        assert kwargs["tokenized_gold_provider"] is tokenized_provider
        assert kwargs["gold_spot_provider"] is spot_provider

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        session = MagicMock()
        service_cls = MagicMock()
        service = service_cls.return_value
        service.sync_tokenized_gold_premium = AsyncMock(
            side_effect=RuntimeError("spot unavailable")
        )

        with (
            patch("core.database.get_session", _make_get_session(session)),
            patch("services.gold.macro_sync.MacroSyncService", service_cls),
        ):
            result = await GoldTokenizedGoldSyncJob().execute(
                _make_context("GoldTokenizedGoldSyncJob")
            )

        assert result.success is False
        assert "spot unavailable" in result.error


class TestJobRegistration:
    def test_jobs_are_registered(self) -> None:
        job_registry.register_module(job_definitions)
        names = job_registry.list_names()
        for job_name in (
            "GoldMacroSyncJob",
            "GoldCftcCotSyncJob",
            "GoldEconomicCalendarSyncJob",
            "GoldTokenizedGoldSyncJob",
        ):
            assert job_name in names

    def test_jobs_are_scheduled(self) -> None:
        from apps.scheduler.app import SchedulerApp

        source = inspect.getsource(SchedulerApp.start)
        for job_name in (
            "GoldMacroSyncJob",
            "GoldCftcCotSyncJob",
            "GoldEconomicCalendarSyncJob",
            "GoldTokenizedGoldSyncJob",
        ):
            assert f'"{job_name}"' in source
