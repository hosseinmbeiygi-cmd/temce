"""HTTP contract for ``GET /api/v1/gold/analytics/macro/live``.

The DB read is stubbed so these tests never touch a real database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db_session
from apps.api.endpoints import gold_analytics
from schemas.api.gold.analytics import MacroLiveResponse
from services.gold.macro_live import MacroLiveResult

BASE = "/api/v1/gold/analytics"
LIVE_PATH = f"{BASE}/macro/live"


@pytest.fixture()
def client(app):
    async def _session():
        yield object()

    app.dependency_overrides[get_db_session] = _session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_db_session, None)


def test_macro_live_available(client, monkeypatch) -> None:
    async def fake_get_macro_live(session):
        return MacroLiveResult(
            available=True,
            missing=[],
            posture={
                "posture": "BULLISH",
                "composite_score": 3,
                "tips_yield": 0.8,
                "dxy_index": 92.0,
                "gold_trend": "up",
            },
            inputs={
                "tips_yield": 0.8,
                "dxy_index": 92.0,
                "gold_trend": "up",
                "tokenized_gold_premium": {"PAXG": -3.31, "XAUT": -3.29},
            },
            tips_staleness_seconds=100.0,
            dxy_staleness_seconds=200.0,
            trend_staleness_seconds=300.0,
            high_vol_window=True,
        )

    monkeypatch.setattr(gold_analytics, "get_gold_macro_live", fake_get_macro_live)

    response = client.get(f"{BASE}/macro/live")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["available"] is True
    assert body["data"]["missing"] == []
    assert body["data"]["posture"]["posture"] == "BULLISH"
    assert body["data"]["high_vol_window"] is True
    assert body["data"]["inputs"]["tokenized_gold_premium"] == {
        "PAXG": -3.31,
        "XAUT": -3.29,
    }


def test_macro_live_response_matches_its_schema(client, monkeypatch) -> None:
    """The 200 body is valid against the declared ``MacroLiveResponse`` model."""

    async def fake_get_macro_live(session):
        return MacroLiveResult(
            available=False,
            missing=["tips_yield", "gold_trend"],
            posture=None,
            inputs={"dxy_index": 92.0},
            dxy_staleness_seconds=200.0,
        )

    monkeypatch.setattr(gold_analytics, "get_gold_macro_live", fake_get_macro_live)

    response = client.get(LIVE_PATH)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True

    # ``extra="forbid"``: this also fails if the route starts emitting a field
    # the declared schema does not carry.
    parsed = MacroLiveResponse.model_validate(body["data"])
    assert parsed.available is False
    assert parsed.missing == ["tips_yield", "gold_trend"]
    assert parsed.posture is None
    assert parsed.inputs == {"dxy_index": 92.0}


def test_macro_live_uses_the_same_response_style_as_sibling_routes(app) -> None:
    """Every analytics route declares the envelope through its return annotation.

    None of them passes ``response_model=`` to the decorator; FastAPI infers the
    model from ``-> ApiResponse[...]``.  ``/feed-health`` is the one deliberate
    exception: it may answer 503 with a raw ``JSONResponse``, so it opts out with
    ``response_model=None``.
    """
    from fastapi.routing import APIRoute

    routes = {
        (route.path, tuple(sorted(route.methods))): route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith(f"{BASE}/")
    }
    live = routes[(LIVE_PATH, ("GET",))]
    posture = routes[(f"{BASE}/macro/posture", ("POST",))]

    assert live.response_model is not None
    assert posture.response_model is not None
    # Both are the same ``ApiResponse[...]`` generic envelope class, differing
    # only in the payload type — i.e. the same style, not a different mechanism.
    assert type(live.response_model) is type(posture.response_model)
    assert live.response_model.model_json_schema()["properties"].keys() == (
        posture.response_model.model_json_schema()["properties"].keys()
    )

    opted_out = {
        path
        for (path, _), route in routes.items()
        if route.response_model is None
    }
    assert opted_out == {f"{BASE}/feed-health"}


def test_macro_live_not_available(client, monkeypatch) -> None:
    async def fake_get_macro_live(session):
        return MacroLiveResult(
            available=False,
            missing=["tips_yield", "gold_trend"],
            posture=None,
            inputs={"dxy_index": 92.0},
            dxy_staleness_seconds=200.0,
        )

    monkeypatch.setattr(gold_analytics, "get_gold_macro_live", fake_get_macro_live)

    response = client.get(f"{BASE}/macro/live")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["available"] is False
    assert "tips_yield" in body["data"]["missing"]
    assert "gold_trend" in body["data"]["missing"]
    assert body["data"]["posture"] is None
    assert body["data"]["high_vol_window"] is False
