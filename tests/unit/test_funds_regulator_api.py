"""Contract tests for /funds/v2/regulator/* endpoints (no DB required)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from apps.api.endpoints.funds_regulator import (  # noqa: E402
    _get_compliance,
    _get_engine,
    _get_ledger,
    _get_recon,
    require_regulator_admin,
)
from apps.api.endpoints.funds_regulator import router as funds_regulator_router  # noqa: E402


def _fake_engine() -> Any:
    engine = MagicMock()
    engine.get_latest = AsyncMock(
        return_value={
            "run_id": 5,
            "valuation_date": "2026-09-18",
            "nav_per_unit": 12_000,
            "net_assets": 1_200_000_000,
            "quality_status": "ESTIMATED",
            "input_hash": "a" * 64,
        }
    )
    engine.list_runs = AsyncMock(return_value=[])
    return engine


def _fake_recon() -> Any:
    recon = MagicMock()
    recon.list_reconciliations = AsyncMock(
        return_value=[
            {
                "recon_run_id": 2,
                "comparability_status": "COMPARABLE",
                "reference_status": "VALID",
                "diff_status": "MATCHED",
                "bps_diff": 3.2,
            }
        ]
    )
    recon.list_breaks = AsyncMock(return_value=[])
    return recon


def _fake_ledger() -> Any:
    ledger = MagicMock()
    ledger.trial_balance = AsyncMock(
        return_value={
            "accounts": [],
            "total_debit": 1_000_000,
            "total_credit": 1_000_000,
            "balanced": True,
        }
    )
    return ledger


def _fake_compliance() -> Any:
    svc = MagicMock()
    svc.list_aml_alerts = AsyncMock(return_value=[])
    svc.list_str_reports = AsyncMock(return_value=[])
    svc.list_committees = AsyncMock(return_value=[])
    svc.list_internal_audits = AsyncMock(return_value=[])
    svc.list_csdi_breaks = AsyncMock(return_value=[])
    svc.log_regulator_access = AsyncMock(return_value=None)
    svc.list_regulator_access_logs = AsyncMock(
        return_value=[
            {
                "log_id": 1,
                "fund_id": "tse:آگاس",
                "endpoint": "/evidence",
                "actor": "SEO",
                "purpose": "audit",
                "created_at": "2026-09-18T10:00:00",
            }
        ]
    )
    return svc


def _fake_admin() -> dict:
    return {"id": "seo-admin", "roles": ["admin"]}


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(funds_regulator_router, prefix="/funds/v2/regulator")
    application.dependency_overrides[_get_engine] = _fake_engine
    application.dependency_overrides[_get_recon] = _fake_recon
    application.dependency_overrides[_get_ledger] = _fake_ledger
    application.dependency_overrides[_get_compliance] = _fake_compliance
    application.dependency_overrides[require_regulator_admin] = _fake_admin
    return application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_evidence_bundle_and_access_log(
    app: FastAPI, client: AsyncClient
) -> None:
    compliance = _fake_compliance()
    app.dependency_overrides[_get_compliance] = lambda: compliance
    resp = await client.get(
        "/funds/v2/regulator/tse:آگاس/evidence?actor=SEO&purpose=audit"
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fund_id"] == "tse:آگاس"
    assert len(data["integrity_hash"]) == 64
    assert data["trial_balance"]["balanced"] is True
    compliance.log_regulator_access.assert_awaited()


async def test_audit_pack_csv(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/regulator/tse:آگاس/audit-pack")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    assert "section,key,value" in body
    assert "integrity,evidence_hash" in body
    assert "ledger,balanced,True" in body


async def test_access_logs_list(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/regulator/access-logs")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 1


async def test_regulator_requires_admin_without_override() -> None:
    """بدون احراز هویت ادمین → 401 (بدون نیاز به DB)."""
    application = FastAPI()
    application.include_router(funds_regulator_router, prefix="/funds/v2/regulator")
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/funds/v2/regulator/tse:آگاس/evidence")
    assert resp.status_code == 401
