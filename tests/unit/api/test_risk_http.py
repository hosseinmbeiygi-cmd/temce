"""🔐 HTTP contract for ``/api/v1/risk``: every figure is scoped, and none is invented.

The DB is stubbed with «no rows», which is exactly the case that used to be dressed up: the
old endpoint shipped eight hardcoded metrics with no portfolio behind them. Here an empty
account must produce empty answers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from apps.api.app import app
from apps.api.dependencies import get_current_user, get_db_session

MOCK_USER = {"sub": "u-1", "username": "tester", "roles": ["user"], "jti": "x", "exp": 9_999_999_999}

ROUTES = ["/api/v1/risk/", "/api/v1/risk/metrics", "/api/v1/risk/alerts",
          "/api/v1/risk/limits", "/api/v1/risk/drawdown"]


def _no_rows_session() -> MagicMock:
    result = MagicMock()
    result.fetchall.return_value = []
    result.scalar_one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


@pytest.fixture()
def client() -> TestClient:
    async def _session() -> AsyncIterator[MagicMock]:
        yield _no_rows_session()

    app.dependency_overrides[get_db_session] = _session
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("route", ROUTES)
def test_every_route_needs_a_user(route: str) -> None:
    """No auth override here: risk figures are portfolio data, not public content."""

    bare = TestClient(app, raise_server_exceptions=False)
    assert bare.get(route).status_code == 401


def test_the_endpoint_set_the_page_actually_calls(client: TestClient) -> None:
    """The page used to fetch four routes that were never mounted, and then showed fakes."""

    for route in ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route
        assert response.json()["success"] is True, route


def test_an_account_without_a_portfolio_reports_no_numbers(client: TestClient) -> None:
    payload = client.get("/api/v1/risk/").json()["data"]

    assert payload["state"] == "NO_PORTFOLIO"
    assert payload["drawdown"] == []
    assert payload["alerts"] == []
    assert all(m["value"] is None for m in payload["metrics"]), "an empty account has no risk figures"
    assert all(m["note"] for m in payload["metrics"])
    assert all(limit["current"] is None for limit in payload["limits"])


def test_the_sharpe_refusal_is_still_announced(client: TestClient) -> None:
    """Keeping the ratio visible-as-refused beats silently dropping it from the list."""

    by_key = {m["key"]: m for m in client.get("/api/v1/risk/metrics").json()["data"]}

    assert by_key["sharpe"]["state"] == "unknown"
    assert "بدون ریسک" in by_key["sharpe"]["note"]
