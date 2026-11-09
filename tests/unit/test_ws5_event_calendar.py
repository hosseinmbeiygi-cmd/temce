"""WS5: Event Calendar — upcoming economic events affecting gold.

RED (before fixes):
  1. Module src.gold_desk.event_calendar does not exist — all tests ImportError.
  2. No GET /gold/calendar endpoint in api.py.

GREEN (after fixes):
  1. src/gold_desk/event_calendar.py created with ScheduledEvent, get_seed_events(),
     get_calendar_events(), refresh_calendar_cache().
  2. GET /gold/calendar endpoint added to src/gold_desk/api.py.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── 1. Module importable ────────────────────────────────────────────────────

def test_import_event_calendar():
    """Module must be importable.

    RED: src/gold_desk/event_calendar.py does not exist.
    GREEN: module created with ScheduledEvent, VALID_CATEGORIES, get_seed_events,
           get_calendar_events, refresh_calendar_cache.
    """
    from src.gold_desk.event_calendar import (  # noqa: F401
        VALID_CATEGORIES,
        ScheduledEvent,
        get_calendar_events,
        get_seed_events,
        refresh_calendar_cache,
    )


# ─── 2. ScheduledEvent dataclass ─────────────────────────────────────────────

def test_scheduled_event_has_required_fields():
    """ScheduledEvent must carry name, scheduled_at, category, importance, source.

    RED: class does not exist.
    GREEN: frozen dataclass with all five fields.
    """
    from src.gold_desk.event_calendar import ScheduledEvent

    from core.time import utc_now_naive

    ev = ScheduledEvent(
        event_name="تصمیم نرخ بهره بانک مرکزی",
        scheduled_at=utc_now_naive() + timedelta(days=7),
        category="rate",
        importance=3,
        source="cbi",
    )
    assert ev.event_name == "تصمیم نرخ بهره بانک مرکزی"
    assert ev.category == "rate"
    assert ev.importance == 3
    assert ev.source == "cbi"


def test_scheduled_event_to_dict_includes_is_past():
    """to_dict() must include is_past flag based on scheduled_at vs now.

    RED: method does not exist.
    GREEN: is_past=True for past events, False for future.
    """
    from src.gold_desk.event_calendar import ScheduledEvent

    from core.time import utc_now_naive

    past_ev = ScheduledEvent(
        event_name="past",
        scheduled_at=utc_now_naive() - timedelta(days=1),
        category="rate",
        importance=1,
        source="cbi",
    )
    future_ev = ScheduledEvent(
        event_name="future",
        scheduled_at=utc_now_naive() + timedelta(days=1),
        category="rate",
        importance=1,
        source="cbi",
    )
    assert past_ev.to_dict()["is_past"] is True
    assert future_ev.to_dict()["is_past"] is False


# ─── 3. Seed events ──────────────────────────────────────────────────────────

def test_seed_events_are_non_empty():
    """get_seed_events() must return at least one event.

    RED: function does not exist.
    GREEN: returns a non-empty list.
    """
    from src.gold_desk.event_calendar import get_seed_events

    events = get_seed_events()
    assert len(events) >= 1, "get_seed_events() must return at least one event"


def test_seed_events_all_have_valid_fields():
    """Every seed event must have non-empty name, valid category, importance 1–3.

    RED: function does not exist.
    GREEN: all seed events pass validation.
    """
    from src.gold_desk.event_calendar import VALID_CATEGORIES, get_seed_events

    for ev in get_seed_events():
        assert ev.event_name, f"empty event_name: {ev}"
        assert ev.category in VALID_CATEGORIES, (
            f"invalid category {ev.category!r} — must be one of {sorted(VALID_CATEGORIES)}"
        )
        assert 1 <= ev.importance <= 3, (
            f"importance {ev.importance} out of range 1–3 for event {ev.event_name!r}"
        )
        assert isinstance(ev.scheduled_at, datetime), (
            f"scheduled_at is not a datetime for {ev.event_name!r}"
        )
        assert ev.source, f"empty source for {ev.event_name!r}"


# ─── 4. Calendar filtering ───────────────────────────────────────────────────

def test_get_calendar_events_excludes_far_future():
    """get_calendar_events(days_ahead=0) must exclude events scheduled tomorrow+.

    RED: function does not exist.
    GREEN: only past/today events returned.
    """
    from src.gold_desk.event_calendar import ScheduledEvent, get_calendar_events

    from core.time import utc_now_naive

    future_only_provider = [
        ScheduledEvent(
            event_name="far-future",
            scheduled_at=utc_now_naive() + timedelta(days=10),
            category="rate",
            importance=1,
            source="test",
        )
    ]

    with patch("src.gold_desk.event_calendar.get_seed_events", return_value=future_only_provider):
        events = get_calendar_events(days_ahead=0)

    for ev in events:
        naive = ev.scheduled_at.replace(tzinfo=None) if ev.scheduled_at.tzinfo else ev.scheduled_at
        assert naive <= utc_now_naive(), (
            f"Event {ev.event_name!r} is in the future but days_ahead=0"
        )


def test_get_calendar_events_sorted_chronologically():
    """get_calendar_events() must return events sorted by scheduled_at ascending.

    RED: function does not exist.
    GREEN: sorted from earliest to latest.
    """
    from src.gold_desk.event_calendar import get_calendar_events

    events = get_calendar_events(days_ahead=365)
    if len(events) >= 2:
        for a, b in zip(events, events[1:]):
            assert a.scheduled_at <= b.scheduled_at, (
                f"Events out of order: {a.event_name!r} ({a.scheduled_at}) "
                f"should come before {b.event_name!r} ({b.scheduled_at})"
            )


# ─── 5. Injectable cache refresh ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_calendar_cache_uses_injectable_provider():
    """refresh_calendar_cache() must accept an injectable events_provider.

    RED: function does not exist.
    GREEN: provider is called; result returned; cache.set called once.
    """
    from src.gold_desk.event_calendar import ScheduledEvent, refresh_calendar_cache

    from core.time import utc_now_naive

    captured_cache_calls: list = []

    def mock_provider():
        return [
            ScheduledEvent(
                event_name="mock-event",
                scheduled_at=utc_now_naive() + timedelta(days=1),
                category="inflation",
                importance=2,
                source="test",
            )
        ]

    class MockCache:
        async def set(self, key, value, ttl=None):
            captured_cache_calls.append((key, value))

        async def get(self, key):
            return None

    result = await refresh_calendar_cache(events_provider=mock_provider, cache=MockCache())

    assert len(result) == 1, "Must return the list from the provider"
    assert result[0].event_name == "mock-event"
    assert len(captured_cache_calls) == 1, "Must call cache.set exactly once"
    key, payload = captured_cache_calls[0]
    assert "golddesk:calendar" in key, f"Unexpected Redis key: {key!r}"
    assert "mock-event" in payload, "Payload must contain the event name"


@pytest.mark.asyncio
async def test_refresh_calendar_cache_empty_provider_returns_empty():
    """refresh_calendar_cache() with empty provider returns [] without writing cache.

    RED: function does not exist.
    GREEN: empty provider → empty list, no cache write.
    """
    from src.gold_desk.event_calendar import refresh_calendar_cache

    cache_calls: list = []

    class MockCache:
        async def set(self, key, value, ttl=None):
            cache_calls.append(key)

        async def get(self, key):
            return None

    result = await refresh_calendar_cache(events_provider=lambda: [], cache=MockCache())
    assert result == [], "Empty provider must return []"
    assert cache_calls == [], "Must not write to cache when provider returns empty list"
