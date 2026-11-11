"""ASGI contract for the new GoldDesk surfaces.

Asserts the *wiring + response shape* of:

  * GET  /gold/portfolio/history       (persisted value series)
  * GET  /gold/portfolio/performance   (TWR + risk + benchmarks)
  * POST /gold/portfolio/snapshot      (capture today's value)
  * GET  /gold/freshness               (data-freshness report)
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_current_user, get_db_session
from src.gold_desk import api as gold_api


def _history_row(day: date) -> SimpleNamespace:
    return SimpleNamespace(
        as_of=day,
        total_value_irt=1_000.0,
        total_cost_irt=900.0,
        net_flow_irt=0.0,
        unpriced_holdings=0,
    )


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(gold_api.router)
    app.dependency_overrides[get_db_session] = lambda: None
    # این‌جا شکل پاسخ مسیرها سنجیده می‌شود، نه احراز هویت.
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test-admin", "roles": ["admin"]}

    performance = SimpleNamespace(
        as_dict=lambda: {
            "window_days": 90,
            "twr_pct": 12.5,
            "concentration_pct": 65.0,
            "benchmarks": {"gold": {"return_pct": 20.0, "relative_pct": -7.5}},
            "unavailable": {},
        }
    )
    captured = SimpleNamespace(
        as_of=date(2026, 10, 14),
        total_value_irt=5_000.0,
        total_cost_irt=4_000.0,
        net_flow_irt=100.0,
        unpriced_holdings=1,
    )
    stubs = {
        "get_hot_snapshot": AsyncMock(return_value={"snapshot_at": "2026-10-14T00:00:00"}),
        "load_value_history": AsyncMock(return_value=[_history_row(date(2026, 10, 14))]),
        "build_performance_report": AsyncMock(return_value=performance),
        "capture_portfolio_value": AsyncMock(return_value=captured),
        "build_freshness_report": AsyncMock(
            return_value={
                "generated_at": "2026-10-14T00:00:00+00:00",
                "overall": "stale",
                "counts": {"ok": 1, "stale": 1, "empty": 0, "missing": 0},
                "sources": [{"key": "gold_snapshots", "status": "ok"}],
            }
        ),
    }
    with pytest.MonkeyPatch.context() as mp:
        for name, mock in stubs.items():
            mp.setattr(gold_api, name, mock)
        yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_portfolio_history_shape(client: TestClient) -> None:
    r = client.get("/gold/portfolio/history?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["points"] == 1
    item = body["data"]["items"][0]
    assert item["as_of"] == "2026-10-14"
    assert item["total_value_irt"] == 1_000.0


def test_portfolio_performance_shape(client: TestClient) -> None:
    r = client.get("/gold/portfolio/performance?days=90")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["twr_pct"] == 12.5
    assert data["concentration_pct"] == 65.0
    assert data["benchmarks"]["gold"]["relative_pct"] == -7.5


def test_portfolio_snapshot_capture(client: TestClient) -> None:
    r = client.post("/gold/portfolio/snapshot")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["as_of"] == "2026-10-14"
    assert data["total_value_irt"] == 5_000.0
    assert data["net_flow_irt"] == 100.0
    assert data["unpriced_holdings"] == 1


def test_freshness_shape(client: TestClient) -> None:
    r = client.get("/gold/freshness")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["overall"] == "stale"
    assert data["sources"][0]["key"] == "gold_snapshots"
    assert isinstance(data["scheduler_jobs"], int)
