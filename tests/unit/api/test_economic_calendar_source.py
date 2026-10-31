"""``GET /economic-calendar`` must serve stored rows, never the static fixture.

The route used to return a hand-written list of events (dated July 2026) as if
it were live data; there is no timestamp to publish for a fixture, which is how
the missing-``data_as_of`` symptom in the audit surfaced. Rows now come from
``gold_economic_calendar_events`` (``GoldEconomicCalendarSyncJob``) and
``data_as_of`` is the newest ``fetched_at`` among the served rows.

Offline: the calendar service is replaced with a fake row list.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from apps.api.endpoints import economic_calendar as endpoint

FETCHED = datetime(2026, 10, 29, 7, 45, tzinfo=UTC)


def _row(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "event_id": "evt-001",
        "event_date": date(2026, 11, 5),
        "event_time": "13:30",
        "title": "نرخ بهره بانک مرکزی",
        "country": "ایران",
        "category": "بانک مرکزی",
        "importance": 3,
        "is_high_volatility": True,
        "source": "seeded",
        "fetched_at": FETCHED,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def stored_rows(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    async def fake_list(session: Any, *, start: Any = None, end: Any = None, limit: int = 100):
        captured.update({"start": start, "end": end, "limit": limit})
        return [_row(), _row(event_id="evt-002", event_date=date(2026, 11, 6), importance=1)]

    monkeypatch.setattr(
        "services.gold.economic_calendar.list_economic_calendar", fake_list
    )
    return captured


async def test_serves_stored_rows_and_the_newest_fetch_time(stored_rows) -> None:
    resp = await endpoint.get_economic_calendar(
        start="2026-11-01",
        end="2026-11-30",
        category=None,
        min_importance=1,
        session=None,  # type: ignore[arg-type]
    )

    assert resp.success is True
    assert [ev["id"] for ev in resp.data["events"]] == ["evt-001", "evt-002"]
    assert resp.data_as_of == FETCHED.isoformat()
    assert resp.data["date_range"] == {"start": "2026-11-01", "end": "2026-11-30"}
    assert stored_rows["start"] == date(2026, 11, 1)
    assert stored_rows["end"] == date(2026, 11, 30)


async def test_static_fixture_is_not_served(stored_rows) -> None:
    """The in-module EVENTS list still exists; it must never reach the wire."""
    resp = await endpoint.get_economic_calendar(
        start="2026-11-01", end="2026-11-30", category=None, min_importance=1,
        session=None,  # type: ignore[arg-type]
    )

    served_ids = {ev["id"] for ev in resp.data["events"]}
    assert served_ids == {"evt-001", "evt-002"}
    assert "ev-001" not in served_ids


async def test_filters_apply_to_stored_rows(stored_rows) -> None:
    resp = await endpoint.get_economic_calendar(
        start="2026-11-01", end="2026-11-30", category="بانک مرکزی",
        min_importance=2, session=None,  # type: ignore[arg-type]
    )

    assert [ev["id"] for ev in resp.data["events"]] == ["evt-001"]


async def test_empty_table_is_explicit_empty_without_a_timestamp(monkeypatch) -> None:
    async def empty(session: Any, **_kwargs: Any) -> list[Any]:
        return []

    monkeypatch.setattr("services.gold.economic_calendar.list_economic_calendar", empty)

    resp = await endpoint.get_economic_calendar(
        start=None, end=None, category=None, min_importance=1,
        session=None,  # type: ignore[arg-type]
    )

    assert resp.success is True
    assert resp.data["events"] == []
    assert resp.data["total"] == 0
    assert resp.data_as_of is None
