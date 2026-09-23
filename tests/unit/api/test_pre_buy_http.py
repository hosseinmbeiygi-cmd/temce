"""🔐 HTTP-level auth chain for ``/api/v1/pre-buy``.

Runs the real app with overrides so the mount + per-endpoint dependency wiring is
validated end to end. DB is stubbed — these tests assert who may call what, not what the
sheets contain (that is covered by the service and engine tests).

``_optional_auth`` at the mount is deliberate: the question bank is public content, while
every route that reads or writes a sheet declares ``Depends(get_current_user)`` itself.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from apps.api.app import app
from apps.api.dependencies import get_current_user, get_db_session

MOCK_USER = {"sub": "u-1", "username": "tester", "roles": ["user"], "jti": "x", "exp": 9_999_999_999}


def _empty_session() -> MagicMock:
    """A session whose ``execute`` resolves to «no row».

    A bare ``AsyncMock`` cannot stand in here: its chained ``.scalar_one_or_none()`` is
    itself a coroutine, which is truthy, so the 404 branch never runs.
    """

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalars.return_value.all.return_value = []
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture()
def client() -> TestClient:
    async def _session():
        yield _empty_session()

    app.dependency_overrides[get_db_session] = _session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_client() -> TestClient:
    async def _session():
        yield _empty_session()

    app.dependency_overrides[get_db_session] = _session
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_catalogue_is_public_and_complete(client: TestClient) -> None:
    res = client.get("/api/v1/pre-buy/catalogue")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["total"] == 115
    assert len(body["data"]["stages"]) == 11
    assert len(body["data"]["stopperCodes"]) == 15


def test_meta_reports_the_document_counts(client: TestClient) -> None:
    data = client.get("/api/v1/pre-buy/meta").json()["data"]
    assert data["questions"] == 115
    assert data["stoppers"] == 15
    assert data["golden"] == 5
    assert sum(data["per_stage"]) == 115


def test_sheet_routes_require_a_user(client: TestClient) -> None:
    for path in ("/api/v1/pre-buy/sheets",):
        assert client.get(path).status_code == 401
    assert client.post("/api/v1/pre-buy/sheets", json={"symbol": "فولاد"}).status_code == 401
    assert client.get("/api/v1/pre-buy/sheets/1").status_code == 401


def test_unknown_sheet_is_404_not_500(auth_client: TestClient) -> None:
    """A session that returns no row must surface as «not yours / not there», never 403."""

    res = auth_client.get("/api/v1/pre-buy/sheets/424242")
    assert res.status_code == 404, res.text
