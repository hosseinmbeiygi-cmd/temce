"""SIL-02/SIL-03 — خطای DB از «یافت نشد» جدا می‌شود و SQL به کلاینت نمی‌رسد."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import apps.api.endpoints.funds as funds_api
import apps.api.endpoints.gold as gold_api
from apps.api.dependencies import get_brsapi_query_service, get_db_session


class _FailingSession:
    async def execute(self, *_args, **_kwargs):
        raise OperationalError("SELECT ...", {}, Exception("column brsapi_nav_records.ins_id does not exist"))


class _EmptySession:
    async def execute(self, *_args, **_kwargs):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))


@pytest.fixture()
def funds_client() -> TestClient:
    app = FastAPI()
    app.include_router(funds_api.router, prefix="/funds")
    yield app
    app.dependency_overrides.clear()


def test_nav_split_read_failure_is_503_not_found_false(funds_client: FastAPI) -> None:
    funds_client.dependency_overrides[get_db_session] = lambda: _FailingSession()
    client = TestClient(funds_client, raise_server_exceptions=False)

    response = client.get("/funds/سیلور/nav-split")

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "NAV_READ_FAILED"
    assert "ins_id" not in response.text


def test_nav_split_without_a_row_still_returns_found_false(funds_client: FastAPI) -> None:
    funds_client.dependency_overrides[get_db_session] = lambda: _EmptySession()
    client = TestClient(funds_client, raise_server_exceptions=False)

    response = client.get("/funds/سیلور/nav-split")

    assert response.status_code == 200
    assert response.json()["found"] is False


class _ExplodingBrsapi:
    async def get_ime_futures(self):
        raise RuntimeError(
            "(psycopg2.errors.UndefinedColumn) column brsapi_ime_futures.bid_volume_1 does not exist"
        )


def test_ime_futures_error_does_not_leak_sql() -> None:
    app = FastAPI()
    app.include_router(gold_api.router, prefix="/gold")
    app.dependency_overrides[get_brsapi_query_service] = lambda: _ExplodingBrsapi()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/gold/ime/futures")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SOURCE_UNAVAILABLE"
    assert "bid_volume_1" not in response.text
    assert "psycopg2" not in response.text
