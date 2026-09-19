"""Contract tests for /funds/v2/ledger/* endpoints (no DB required)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from apps.api.endpoints.funds_ledger import _get_ledger  # noqa: E402
from apps.api.endpoints.funds_ledger import router as funds_ledger_router  # noqa: E402
from services.fund_read_through import StaleResult  # noqa: E402

_TRIAL = {
    "accounts": [
        {
            "account_code": "CASH",
            "account_name": "نقد",
            "account_type": "ASSET",
            "normal_side": "DEBIT",
            "debit": 1_000_000,
            "credit": 0,
            "balance": 1_000_000,
        }
    ],
    "total_debit": 1_000_000,
    "total_credit": 1_000_000,
    "balanced": True,
}


def _fake_ledger() -> Any:
    ledger = MagicMock()
    ledger.record_unit_movement = AsyncMock(
        return_value=StaleResult(
            data={
                "created": True,
                "movement_id": 1,
                "reference": "ISSUE-2026-09-18-100",
                "fund_id": "tse:آگاس",
                "movement_type": "ISSUE",
                "units": 100,
                "amount": 5_000_000,
                "entry_id": 9,
            },
            freshness="live",
            fetched_from="db",
        )
    )
    ledger.trial_balance = AsyncMock(return_value=_TRIAL)
    ledger.list_entries = AsyncMock(return_value=[])
    ledger.list_unit_movements = AsyncMock(return_value=[])
    ledger.reverse_entry = AsyncMock(return_value={"entry_id": 10, "created": True})
    return ledger


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(funds_ledger_router, prefix="/funds/v2/ledger")
    application.dependency_overrides[_get_ledger] = _fake_ledger
    return application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_record_unit_movement_contract(client: AsyncClient) -> None:
    resp = await client.post(
        "/funds/v2/ledger/tse:آگاس/unit-movements",
        json={
            "movement_type": "ISSUE",
            "movement_date": "2026-09-18",
            "units": 100,
            "price_per_unit": 50_000,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["entry_id"] == 9
    assert data["movement_type"] == "ISSUE"


async def test_record_unit_movement_validation_error(client: AsyncClient) -> None:
    resp = await client.post(
        "/funds/v2/ledger/tse:آگاس/unit-movements",
        json={"movement_type": "ISSUE", "movement_date": "2026-09-18", "units": 0},
    )
    assert resp.status_code == 422  # pydantic gt=0


async def test_trial_balance_contract(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/ledger/tse:آگاس/trial-balance")
    assert resp.status_code == 200
    assert resp.json()["data"]["balanced"] is True


async def test_entries_and_movements_list(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/ledger/tse:آگاس/entries?limit=10")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 0

    resp2 = await client.get("/funds/v2/ledger/tse:آگاس/unit-movements")
    assert resp2.status_code == 200
    assert resp2.json()["data"]["movements"] == []


async def test_reverse_entry_contract(client: AsyncClient) -> None:
    resp = await client.post("/funds/v2/ledger/entries/9/reverse", json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["entry_id"] == 10
