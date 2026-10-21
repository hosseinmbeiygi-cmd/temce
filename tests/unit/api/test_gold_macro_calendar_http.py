"""HTTP contract for the gold economic-calendar endpoints.

``GET  /api/v1/gold/analytics/macro/calendar``     — stored CPI/NFP/FOMC events
``GET  /api/v1/gold/analytics/macro/iran-events``  — Iran manual-entry events
``POST /api/v1/gold/analytics/macro/iran-events``  — manual entry (auth required)

The DB is stubbed so these tests never touch a real database.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db_session
from apps.api.endpoints import gold_analytics
from core.security.tokens import create_access_token

BASE = "/api/v1/gold/analytics"


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Writes under ``/api/v1/gold/`` are gated by SecurityMiddleware."""
    token = create_access_token({"sub": "operator", "roles": ["user"], "type": "access"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(app):
    async def _session():
        yield object()

    app.dependency_overrides[get_db_session] = _session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_db_session, None)


def _calendar_row(**overrides):
    defaults = {
        "event_id": "cpi-2026-10-15",
        "event_date": date(2026, 10, 15),
        "event_time": "16:30",
        "title": "US CPI",
        "country": "US",
        "category": "CPI",
        "importance": 3,
        "is_high_volatility": True,
        "source": "seeded",
    }
    defaults.update(overrides)
    row = type("Row", (), defaults)
    return row


def _iran_row(**overrides):
    defaults = {
        "event_id": "iran-fx-2026-10-20",
        "event_date": date(2026, 10, 20),
        "event_time": None,
        "title": "Iran FX decision",
        "category": "FX",
        "importance": 2,
        "note": "manual",
        "is_high_volatility": True,
    }
    defaults.update(overrides)
    return type("Row", (), defaults)


class TestMacroCalendar:
    def test_list_calendar(self, client, monkeypatch) -> None:
        async def fake_list(session, *, start=None, end=None, limit=100):
            assert limit == 100
            return [_calendar_row()]

        monkeypatch.setattr(gold_analytics, "list_economic_calendar", fake_list)

        response = client.get(f"{BASE}/macro/calendar")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["data"][0]["event_id"] == "cpi-2026-10-15"
        assert body["data"][0]["category"] == "CPI"
        assert body["data"][0]["is_high_volatility"] is True
        assert body["data"][0]["event_date"] == "2026-10-15"

    def test_list_calendar_empty(self, client, monkeypatch) -> None:
        async def fake_list(session, *, start=None, end=None, limit=100):
            return []

        monkeypatch.setattr(gold_analytics, "list_economic_calendar", fake_list)

        response = client.get(f"{BASE}/macro/calendar")

        assert response.status_code == 200, response.text
        assert response.json()["data"] == []


class TestIranManualEvents:
    def test_list_iran_events(self, client, monkeypatch) -> None:
        async def fake_list(session, *, start=None, end=None, limit=100):
            return [_iran_row()]

        monkeypatch.setattr(gold_analytics, "list_iran_manual_events", fake_list)

        response = client.get(f"{BASE}/macro/iran-events")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["data"][0]["event_id"] == "iran-fx-2026-10-20"
        assert body["data"][0]["is_high_volatility"] is True

    def test_post_iran_event(self, client, monkeypatch, auth_headers) -> None:
        captured: dict[str, object] = {}

        async def fake_add(session, **kwargs):
            captured.update(kwargs)
            return _iran_row(
                event_id=kwargs["event_id"],
                event_date=kwargs["event_date"],
                event_time=kwargs.get("event_time"),
                title=kwargs.get("title"),
                category=kwargs.get("category"),
                importance=kwargs.get("importance"),
                note=kwargs.get("note"),
                is_high_volatility=kwargs.get("is_high_volatility", False),
            )

        monkeypatch.setattr(gold_analytics, "add_iran_manual_event", fake_add)

        response = client.post(
            f"{BASE}/macro/iran-events",
            json={
                "event_id": "iran-fx-2026-10-20",
                "event_date": "2026-10-20",
                "title": "Iran FX decision",
                "category": "FX",
                "importance": 2,
                "note": "manual",
                "is_high_volatility": True,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["data"]["event_id"] == "iran-fx-2026-10-20"
        assert body["data"]["event_date"] == "2026-10-20"
        assert body["data"]["is_high_volatility"] is True
        # The service receives the caller's fields verbatim.
        assert captured["event_id"] == "iran-fx-2026-10-20"
        assert captured["event_date"] == date(2026, 10, 20)
        assert captured["is_high_volatility"] is True

    def test_post_iran_event_requires_auth(self, client) -> None:
        """Without a token the manual entry is rejected — it is a write."""
        response = client.post(
            f"{BASE}/macro/iran-events",
            json={
                "event_id": "iran-fx-2026-10-20",
                "event_date": "2026-10-20",
            },
        )

        assert response.status_code == 401, response.text
        assert response.json()["code"] == "AUTH_REQUIRED"

    def test_post_iran_event_validates_payload(self, client, auth_headers) -> None:
        response = client.post(
            f"{BASE}/macro/iran-events",
            json={"event_date": "2026-10-20"},
            headers=auth_headers,
        )

        assert response.status_code == 422, response.text
