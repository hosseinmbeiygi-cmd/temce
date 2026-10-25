"""``/gold/metrics`` فقط با Bearer API-token دارای scope «metrics».

JWT session هیچ نقشی ندارد و توکن با scope دیگر هم پذیرفته نمی‌شود.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.gold_desk.api as gold_api
import src.gold_desk.api_token as api_token


def _info(*scopes: str) -> SimpleNamespace:
    return SimpleNamespace(token_id="test", name="test", scopes=list(scopes), enabled=True)


@pytest.fixture()
def client(monkeypatch) -> TestClient:
    async def _verify(token: str):
        if token == "metrics-token":
            return _info("metrics")
        if token == "read-token":
            return _info("read")
        if token == "admin-token":
            return _info("admin")
        return None

    monkeypatch.setattr(api_token, "verify_token", _verify)

    app = FastAPI()
    app.include_router(gold_api.anonymous_router)
    return TestClient(app)


def test_metrics_accepts_bearer_token_with_metrics_scope(client: TestClient) -> None:
    response = client.get("/gold/metrics", headers={"Authorization": "Bearer metrics-token"})

    assert response.status_code == 200, response.text
    assert "golddesk_snapshots_total" in response.text


def test_metrics_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/gold/metrics")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_metrics_rejects_unknown_token(client: TestClient) -> None:
    response = client.get("/gold/metrics", headers={"Authorization": "Bearer nope"})

    assert response.status_code == 401


def test_metrics_rejects_jwt_session_token(client: TestClient) -> None:
    """توکن JWT (بدون رکورد API token) پذیرفته نمی‌شود."""
    response = client.get(
        "/gold/metrics",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("token", ["read-token", "admin-token"])
def test_metrics_rejects_tokens_with_another_scope(client: TestClient, token: str) -> None:
    response = client.get("/gold/metrics", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_metrics_route_sits_on_the_token_gated_router() -> None:
    """مسیر از گیت JWT خارج است، ولی توکن‌محور: دقیقاً روی anonymous_router."""
    anonymous_paths = {route.path for route in gold_api.anonymous_router.routes}
    personal_paths = {route.path for route in gold_api.router.routes}

    assert "/gold/metrics" in anonymous_paths
    assert "/gold/metrics" not in personal_paths
