"""Regression: personal data must be scoped to its owner.

Audit SEC-02 — any authenticated user could mint an ``admin``-scoped GoldDesk
API token (and list/revoke everyone's) because the token routes carried only
the mount-level "a real user" gate.

Audit SEC-03 — ``/portfolios`` listed and returned every user's portfolio; the
service never saw the caller and the repository had no owner predicate.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

# ── SEC-02: token administration is admin-only ──────────────────────────────


class _Request:
    def __init__(self, authorization: str = "Bearer test-token") -> None:
        self.headers = {"authorization": authorization}


async def test_admin_gate_rejects_a_regular_user(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.api import dependencies as deps
    from src.gold_desk import api as gold_api

    async def _regular_user(authorization: str = "") -> dict:
        return {"sub": "user-2", "roles": ["user"]}

    monkeypatch.setattr(deps, "get_current_user", _regular_user)

    with pytest.raises(HTTPException) as exc:
        await gold_api._require_admin_user(_Request())

    assert exc.value.status_code == 403


async def test_admin_gate_allows_an_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.api import dependencies as deps
    from src.gold_desk import api as gold_api

    async def _admin(authorization: str = "") -> dict:
        return {"sub": "user-1", "roles": ["admin"]}

    monkeypatch.setattr(deps, "get_current_user", _admin)

    user = await gold_api._require_admin_user(_Request())

    assert user["roles"] == ["admin"]


async def test_http_token_mint_is_forbidden_for_a_regular_user(client) -> None:
    """End-to-end: a *real* user JWT reaches the route and is refused by role."""
    from core.security.tokens import create_access_token

    token = create_access_token({"sub": "2", "roles": ["user"]})
    response = await client.post(
        "/api/v1/gold/tokens",
        params={"name": "escalation", "scopes": "admin"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403, response.text


# ── SEC-03: portfolios are owner-scoped ────────────────────────────────────


class _FakePortfolioRepo:
    def __init__(self) -> None:
        self.list_owner: object = "unset"
        self.get_owner: object = "unset"
        self.saved_owner: object = "unset"

    async def list_owned(self, owner_id: str | None = None, page: int = 1, page_size: int = 100):
        from core.result import Result

        self.list_owner = owner_id
        return Result.ok(SimpleNamespace(items=[]))

    async def get(self, portfolio_id: str):
        from core.result import Result

        return Result.ok(
            SimpleNamespace(
                id=portfolio_id,
                name="p",
                description="",
                initial_capital=0.0,
                current_capital=0.0,
                currency="IRR",
            )
        )

    async def get_owned(self, portfolio_id: str, owner_id: str | None = None):

        self.get_owner = owner_id
        return await self.get(portfolio_id)

    async def get_positions(self, portfolio_id: str):
        from core.result import Result

        return Result.ok([])

    async def save(self, entity):
        from core.result import Result

        self.saved_owner = getattr(entity, "owner_id", "unset")
        return Result.ok(entity)


def _service_with(repo: _FakePortfolioRepo):
    from services.portfolio_service import PortfolioService

    service = PortfolioService(session=None)  # type: ignore[arg-type]
    service.repo = repo
    return service


async def test_list_portfolios_forwards_the_caller_as_owner() -> None:
    repo = _FakePortfolioRepo()
    service = _service_with(repo)

    await service.list_portfolios(owner_id="user-2")

    assert repo.list_owner == "user-2"


async def test_get_portfolio_forwards_the_caller_as_owner() -> None:
    repo = _FakePortfolioRepo()
    service = _service_with(repo)

    await service.get_portfolio("port-1", owner_id="user-2")

    assert repo.get_owner == "user-2"


async def test_create_portfolio_records_the_owner() -> None:
    repo = _FakePortfolioRepo()
    service = _service_with(repo)

    await service.create_portfolio("mine", owner_id="user-2")

    assert repo.saved_owner == "user-2"


class _RecordingPortfolioService:
    def __init__(self) -> None:
        self.scopes: list[object] = []

    async def list_portfolios(self, owner_id: str | None = None):
        from core.result import Result

        self.scopes.append(owner_id)
        return Result.ok({"items": [], "total": 0})


async def test_http_list_scopes_a_regular_user_to_their_own_id(user_client, app) -> None:
    from apps.api.dependencies import get_portfolio_service

    fake = _RecordingPortfolioService()
    app.dependency_overrides[get_portfolio_service] = lambda: fake

    response = await user_client.get("/api/v1/portfolios/")

    assert response.status_code == 200, response.text
    assert fake.scopes == ["2"]  # tests/unit/conftest.py::_MOCK_USER


async def test_http_list_does_not_filter_for_an_admin(admin_client, app) -> None:
    from apps.api.dependencies import get_portfolio_service

    fake = _RecordingPortfolioService()
    app.dependency_overrides[get_portfolio_service] = lambda: fake

    response = await admin_client.get("/api/v1/portfolios/")

    assert response.status_code == 200, response.text
    assert fake.scopes == [None]
