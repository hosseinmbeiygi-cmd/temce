"""دارایی soft-delete‌شده با id رد می‌شود (بدون دیتابیس).

* ``record_trade`` برای هر معاملهٔ دارای ``holding_id``: دارایی ناموجود ⇒ 404 و
  دارایی حذف‌نرم‌شده ⇒ 409.
* ``DELETE /gold/portfolio/holdings/{id}`` روی دارایی حذف‌شده بدون
  ``?force=true`` هم 409 می‌دهد؛ با force حذف سخت انجام می‌شود.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.gold_desk.api as gold_api
from apps.api.dependencies import get_current_user, get_db_session
from src.gold_desk.portfolio import (
    HoldingDeletedError,
    HoldingNotFoundError,
    record_trade,
)


class FakeSession:
    """حداقل session لازم برای این مسیرها."""

    def __init__(self, holding=None) -> None:
        self.holding = holding
        self.deleted: list[object] = []
        self.added: list[object] = []
        self.commits = 0

    async def get(self, _model, _pk):
        return self.holding

    def add(self, obj) -> None:
        self.added.append(obj)

    async def delete(self, obj) -> None:
        self.deleted.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _obj) -> None:
        return None


def _holding(*, deleted: bool = False):
    return SimpleNamespace(
        id=11,
        buy_price=100.0,
        deleted_at="2026-10-20T00:00:00" if deleted else None,
        symbol="IR_COIN_EMAMI",
    )


@pytest.fixture()
def api_client():
    app = FastAPI()
    app.include_router(gold_api.router)
    # These route tests predate ownership and mount the router without the
    # production auth mount; inject an admin identity so scoping is a no-op.
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "test-admin",
        "roles": ["admin"],
    }
    yield app
    app.dependency_overrides.clear()


def _client(app: FastAPI, session: FakeSession) -> TestClient:
    app.dependency_overrides[get_db_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


# ── Service level ────────────────────────────────────────────


async def test_sell_on_soft_deleted_holding_is_rejected() -> None:
    session = FakeSession(_holding(deleted=True))

    with pytest.raises(HoldingDeletedError):
        await record_trade(
            session,
            symbol="IR_COIN_EMAMI",
            action="sell",
            quantity=1.0,
            price=110.0,
            amount_irt=110.0,
            holding_id=11,
        )

    assert session.added == []
    assert session.commits == 0


async def test_missing_holding_is_rejected() -> None:
    session = FakeSession(None)

    with pytest.raises(HoldingNotFoundError):
        await record_trade(
            session,
            symbol="IR_COIN_EMAMI",
            action="buy",
            quantity=1.0,
            price=110.0,
            amount_irt=110.0,
            holding_id=999,
        )

    assert session.added == []


async def test_active_holding_still_records_the_trade() -> None:
    session = FakeSession(_holding())

    trade = await record_trade(
        session,
        symbol="IR_COIN_EMAMI",
        action="sell",
        quantity=2.0,
        price=110.0,
        amount_irt=220.0,
        holding_id=11,
    )

    assert trade.pnl_irt == pytest.approx(20.0)
    assert session.added == [trade]
    assert session.commits == 1


# ── HTTP level ───────────────────────────────────────────────


def test_post_trade_maps_deleted_holding_to_409(api_client: FastAPI) -> None:
    client = _client(api_client, FakeSession(_holding(deleted=True)))

    response = client.post(
        "/gold/portfolio/trades",
        json={
            "symbol": "IR_COIN_EMAMI",
            "action": "sell",
            "quantity": 1.0,
            "price": 110.0,
            "amount_irt": 110.0,
            "holding_id": 11,
        },
    )

    assert response.status_code == 409
    assert "soft-deleted" in response.json()["detail"]


def test_post_trade_maps_missing_holding_to_404(api_client: FastAPI) -> None:
    client = _client(api_client, FakeSession(None))

    response = client.post(
        "/gold/portfolio/trades",
        json={
            "symbol": "IR_COIN_EMAMI",
            "action": "buy",
            "quantity": 1.0,
            "price": 110.0,
            "amount_irt": 110.0,
            "holding_id": 999,
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_delete_holding_rejects_already_soft_deleted_without_force(api_client: FastAPI) -> None:
    session = FakeSession(_holding(deleted=True))
    client = _client(api_client, session)

    response = client.delete("/gold/portfolio/holdings/11")

    assert response.status_code == 409
    assert "force" in response.json()["detail"]
    assert session.deleted == []
    assert session.commits == 0


def test_delete_holding_hard_deletes_only_with_force(api_client: FastAPI) -> None:
    holding = _holding(deleted=True)
    session = FakeSession(holding)
    client = _client(api_client, session)

    response = client.delete("/gold/portfolio/holdings/11?force=true")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert session.deleted == [holding]


def test_delete_active_holding_sets_deleted_at(api_client: FastAPI) -> None:
    holding = _holding()
    session = FakeSession(holding)
    client = _client(api_client, session)

    response = client.delete("/gold/portfolio/holdings/11")

    assert response.status_code == 200
    assert holding.deleted_at is not None
    assert session.deleted == []
    assert session.commits == 1


def test_delete_missing_holding_is_404(api_client: FastAPI) -> None:
    client = _client(api_client, FakeSession(None))

    response = client.delete("/gold/portfolio/holdings/404")

    assert response.status_code == 404
