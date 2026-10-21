"""Unit tests for ``MacroSyncService``.

No network or real database — providers are injected and sessions are mocked.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.gold_macro import GoldEconomicCalendarEventModel
from services.gold.macro_sync import (
    DEFAULT_STALENESS_SECONDS,
    HIGH_VOLATILITY_CATEGORIES,
    MacroSyncService,
    SyncResult,
)


def _make_session() -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


def _obs(series_id: str, date_str: str, value: float) -> dict:
    return {
        "series_id": series_id,
        "observation_date": date_str,
        "value": value,
        "previous_value": None,
        "change": None,
        "provenance": {"provider": "FRED", "series_id": series_id},
    }


def _cftc_obs(report_date: str, net: int | None = 33_000) -> dict:
    return {
        "report_date": report_date,
        "managed_money_long": 45_000 if net is not None else None,
        "managed_money_short": 12_000 if net is not None else None,
        "managed_money_net": net,
        "managed_money_net_change": 4_000 if net is not None else None,
        "commercial_long": 90_000,
        "commercial_short": 20_000,
        "commercial_net": 70_000,
        "open_interest": 500_000,
        "market_name": "GOLD - COMEX",
        "provenance": {"provider": "CFTC", "dataset": "72hh-3qpy"},
    }


@pytest.mark.asyncio
async def test_sync_fred_upserts_both_indicators() -> None:
    session = _make_session()
    fred = MagicMock()
    fred.fetch.return_value = [
        _obs("DFII10", "2026-10-15", 0.85),
        _obs("DTWEXBGS", "2026-10-15", 104.5),
    ]
    service = MacroSyncService(session, fred_provider=fred)
    result = await service.sync_fred_indicators()

    assert result.ok
    assert result.upserted == 2
    assert result.job_type == "fred_macro_indicators"
    assert session.add.call_count == 2
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sync_fred_idempotent_skips_existing() -> None:
    session = _make_session()
    existing = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=existing)))))

    fred = MagicMock()
    fred.fetch.return_value = [_obs("DFII10", "2026-10-15", 0.85)]
    service = MacroSyncService(session, fred_provider=fred)
    result = await service.sync_fred_indicators()

    assert result.skipped == 1  # already stored → not re-added
    assert result.upserted == 0
    assert session.add.call_count == 0


@pytest.mark.asyncio
async def test_indicator_lookup_binds_a_datetime_not_a_string() -> None:
    """A ``timestamptz`` column must never be compared to a bare string.

    PostgreSQL rejects ``timestamptz = varchar``; binding the raw date string
    made every indicator upsert fail on a real database while the mocked
    unit tests still passed.
    """
    captured: dict[str, object] = {}

    def execute_side_effect(statement, *args, **kwargs):
        captured["params"] = statement.compile().params
        result = MagicMock()
        result.scalars.return_value.first.return_value = None
        result.scalars.return_value.all.return_value = []
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=execute_side_effect)
    session.commit = AsyncMock()

    fred = MagicMock()
    fred.fetch.return_value = [_obs("DFII10", "2026-10-15", 0.85)]
    service = MacroSyncService(session, fred_provider=fred)
    result = await service.sync_fred_indicators()

    assert result.ok
    params = captured["params"]
    as_of_param = next(v for k, v in params.items() if k.startswith("as_of"))
    assert isinstance(as_of_param, datetime)
    assert as_of_param.tzinfo is not None
    assert as_of_param == datetime(2026, 10, 15, 0, 0, tzinfo=UTC)

    # The stored row carries the same aware instant.
    row = session.add.call_args_list[0].args[0]
    assert row.as_of == datetime(2026, 10, 15, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_sync_fred_empty_table_adds_no_rows() -> None:
    """An empty ``gold_macro_indicators`` table + no observations stays empty."""
    session = _make_session()
    fred = MagicMock()
    fred.fetch.return_value = []
    service = MacroSyncService(session, fred_provider=fred)
    result = await service.sync_fred_indicators()

    assert result.ok is True
    assert result.upserted == 0
    assert result.skipped == 0
    assert result.errors == []
    session.add.assert_not_called()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sync_fred_provider_error_recorded() -> None:
    session = _make_session()
    fred = MagicMock()
    fred.fetch.side_effect = RuntimeError("network down")
    service = MacroSyncService(
        session, fred_provider=fred, retry_attempts=1, retry_base_delay=0.0
    )
    result = await service.sync_fred_indicators()

    assert not result.ok
    assert "network down" in result.errors[0]


@pytest.mark.asyncio
async def test_sync_cftc_upserts_with_percentile() -> None:
    session = _make_session()
    cftc = MagicMock()
    cftc.fetch.return_value = [_cftc_obs("2026-10-09", 33_000)]
    service = MacroSyncService(session, cftc_provider=cftc)
    result = await service.sync_cftc_cot_gold()

    assert result.ok
    assert result.upserted == 1
    assert session.add.call_count == 1
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sync_cftc_skips_existing_report_date() -> None:
    existing = MagicMock()
    existing.report_date = date(2026, 10, 9)
    existing.managed_money_net = 33_000

    session = _make_session()
    session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[existing]))))
    )
    cftc = MagicMock()
    cftc.fetch.return_value = [_cftc_obs("2026-10-09", 33_000)]
    service = MacroSyncService(session, cftc_provider=cftc)
    result = await service.sync_cftc_cot_gold()

    assert result.skipped == 1
    assert result.upserted == 0


@pytest.mark.asyncio
async def test_sync_cftc_empty_table_adds_no_rows() -> None:
    """An empty ``gold_cot_positions`` table + no reports stays empty."""
    session = _make_session()
    cftc = MagicMock()
    cftc.fetch.return_value = []
    service = MacroSyncService(session, cftc_provider=cftc)
    result = await service.sync_cftc_cot_gold()

    assert result.ok is True
    assert result.upserted == 0
    assert result.skipped == 0
    assert result.errors == []
    session.add.assert_not_called()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sync_economic_calendar_upserts_events() -> None:
    session = _make_session()
    calendar = MagicMock()
    calendar.fetch.return_value = [
        {
            "event_id": "cpi-2026-10-15",
            "event_date": "2026-10-15",
            "event_time": "08:30",
            "title": "CPI m/m",
            "country": "US",
            "category": "CPI",
            "importance": 3,
            "source": "seeded",
        },
        {
            "event_id": "fomc-2026-10-28",
            "event_date": "2026-10-28",
            "event_time": "14:00",
            "title": "FOMC decision",
            "country": "US",
            "category": "FOMC",
            "importance": 3,
            "source": "seeded",
        },
    ]
    service = MacroSyncService(session, calendar_provider=calendar)
    result = await service.sync_economic_calendar()

    assert result.ok
    assert result.upserted == 2
    assert session.add.call_count == 2
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sync_economic_calendar_records_a_reschedule_as_new_information() -> None:
    """A moved event updates its date *and* refreshes ``fetched_at``.

    The refreshed stamp is the "known since" provenance: the point-in-time
    feature block must not back-date the new date into an earlier value.
    """
    session = _make_session()
    existing = GoldEconomicCalendarEventModel(
        event_id="cpi-2026-10-15",
        event_date=date(2026, 10, 15),
        category="CPI",
        fetched_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    result_mock = MagicMock()
    result_mock.scalars.return_value.first.return_value = existing
    session.execute = AsyncMock(return_value=result_mock)

    calendar = MagicMock()
    calendar.fetch.return_value = [
        {"event_id": "cpi-2026-10-15", "event_date": "2026-10-16", "category": "CPI"}
    ]
    clock = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
    service = MacroSyncService(session, calendar_provider=calendar, clock=lambda: clock)

    result = await service.sync_economic_calendar()

    assert result.upserted == 1
    assert result.skipped == 0
    assert existing.event_date == date(2026, 10, 16)
    assert existing.fetched_at == clock
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_insert_iran_manual_event_idempotent() -> None:
    session = _make_session()
    service = MacroSyncService(session)

    row = await service.insert_iran_manual_event(
        event_id="iran-fx-2026-10-20",
        event_date=date(2026, 10, 20),
        title="FX auction",
        category="FX",
        is_high_volatility=True,
    )
    assert row.event_id == "iran-fx-2026-10-20"
    assert row.is_high_volatility is True
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_insert_iran_manual_event_returns_existing() -> None:
    existing = MagicMock()
    existing.event_id = "iran-fx-2026-10-20"
    session = _make_session()
    session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=existing))))
    )
    service = MacroSyncService(session)
    row = await service.insert_iran_manual_event(
        event_id="iran-fx-2026-10-20",
        event_date=date(2026, 10, 20),
    )
    assert row is existing
    session.commit.assert_not_awaited()


def test_sync_result_defaults() -> None:
    result = SyncResult(job_type="test")
    assert result.ok is False
    assert result.upserted == 0
    assert result.errors == []


def test_high_vol_categories() -> None:
    assert HIGH_VOLATILITY_CATEGORIES == ("CPI", "NFP", "FOMC")


def test_default_staleness_seconds() -> None:
    assert DEFAULT_STALENESS_SECONDS == 7 * 24 * 60 * 60
