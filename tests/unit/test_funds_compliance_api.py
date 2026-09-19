"""Contract tests for /funds/v2/compliance/* endpoints (no DB required)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from apps.api.endpoints.funds_compliance import _get_compliance, _get_tax  # noqa: E402
from apps.api.endpoints.funds_compliance import router as funds_compliance_router  # noqa: E402
from services.fund_read_through import StaleResult  # noqa: E402


def _fake_service() -> Any:
    svc = MagicMock()
    svc.list_aml_alerts = AsyncMock(return_value=[])
    svc.generate_aml_alerts = AsyncMock(
        return_value=StaleResult(data={"alerts_created": 2, "scanned": 10}, freshness="live")
    )
    svc.create_str = AsyncMock(
        return_value={"str_id": 1, "fund_id": "tse:آگاس", "status": "DRAFT", "due_at": "x"}
    )
    svc.list_str_reports = AsyncMock(return_value=[])
    svc.submit_str = AsyncMock(return_value={"str_id": 1, "status": "SUBMITTED"})
    svc.list_sharia_approvals = AsyncMock(return_value=[])
    svc.upsert_sharia_approval = AsyncMock(
        return_value={"approval_id": 1, "approval_ref": "FIQH-1", "status": "APPROVED"}
    )
    svc.list_rpt = AsyncMock(return_value=[])
    svc.record_rpt = AsyncMock(return_value={"rpt_id": 1, "fund_id": "tse:آگاس"})
    svc.list_complaints = AsyncMock(return_value=[])
    svc.record_complaint = AsyncMock(return_value={"complaint_id": 1})
    svc.list_prospectus_versions = AsyncMock(return_value=[])
    svc.record_prospectus_version = AsyncMock(
        return_value={"prospectus_id": 1, "fund_id": "tse:آگاس", "version": "v2"}
    )
    svc.list_lifecycle_events = AsyncMock(return_value=[])
    svc.record_lifecycle_event = AsyncMock(return_value={"event_id": 1})
    svc.import_csdi_statement = AsyncMock(return_value={"statement_id": 1})
    svc.reconcile_csdi = AsyncMock(
        return_value=StaleResult(
            data={
                "fund_id": "tse:آگاس",
                "status": "BREACH",
                "internal_units": 1000,
                "csdi_units": 1005,
                "units_diff": 5,
                "break_id": 7,
            },
            freshness="live",
        )
    )
    svc.list_csdi_breaks = AsyncMock(return_value=[])
    svc.list_committees = AsyncMock(return_value=[])
    svc.record_committee = AsyncMock(return_value={"committee_id": 1})
    svc.list_internal_audits = AsyncMock(return_value=[])
    svc.record_internal_audit = AsyncMock(return_value={"audit_id": 1})
    svc.list_disciplinary_cases = AsyncMock(return_value=[])
    svc.record_disciplinary_case = AsyncMock(return_value={"case_id": 1})
    svc.list_insurance_policies = AsyncMock(return_value=[])
    svc.record_insurance_policy = AsyncMock(return_value={"policy_id": 1})
    svc.export_str_payload = AsyncMock(
        return_value={"format": "FIU-STR-JSON", "report": {"internal_id": 1}}
    )
    return svc


def _fake_tax() -> Any:
    tax = MagicMock()
    tax.list_rules = AsyncMock(
        return_value=[{"tax_type": "TRANSFER_05", "rate": 0.005, "exempt": False}]
    )
    tax.calculate = AsyncMock(
        return_value={
            "tax_id": 1,
            "fund_id": "tse:آگاس",
            "tax_type": "TRANSFER_05",
            "base_amount": 1_000_000_000,
            "rate": 0.005,
            "tax_amount": 5_000_000,
            "exempt": False,
            "exemption_ref": "ARTICLE-143-MOKARRAR",
        }
    )
    tax.summary = AsyncMock(
        return_value={"fund_id": "tse:آگاس", "items": [], "total_tax": 5_000_000}
    )
    tax.calculate_from_trades = AsyncMock(
        return_value={
            "tax_id": 2,
            "fund_id": "tse:آگاس",
            "period_label": "1405-06",
            "tax_type": "TRANSFER_05",
            "base_amount": 3_000_000,
            "tax_amount": 15_000,
            "trade_count": 2,
            "rate": 0.005,
            "exempt": False,
        }
    )
    return tax


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(funds_compliance_router, prefix="/funds/v2/compliance")
    application.dependency_overrides[_get_compliance] = _fake_service
    application.dependency_overrides[_get_tax] = _fake_tax
    return application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_aml_alerts_list_and_generate(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/compliance/tse:آگاس/aml/alerts")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 0

    resp2 = await client.post(
        "/funds/v2/compliance/tse:آگاس/aml/alerts/generate",
        json={"cash_threshold": 500_000_000},
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["alerts_created"] == 2


async def test_str_create_and_submit(client: AsyncClient) -> None:
    resp = await client.post(
        "/funds/v2/compliance/tse:آگاس/aml/str",
        json={"reason": "تراکنش مشکوک", "amount": 900_000_000},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "DRAFT"

    resp2 = await client.post("/funds/v2/compliance/aml/str/1/submit")
    assert resp2.status_code == 200
    assert resp2.json()["data"]["status"] == "SUBMITTED"


async def test_sharia_approval_contract(client: AsyncClient) -> None:
    resp = await client.post(
        "/funds/v2/compliance/sharia/approvals",
        json={"approval_ref": "FIQH-1", "instrument_symbol": "فولاد", "instrument_type": "EQUITY"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "APPROVED"


async def test_governance_and_lifecycle_contracts(client: AsyncClient) -> None:
    resp = await client.post(
        "/funds/v2/compliance/tse:آگاس/rpt",
        json={"counterparty": "شرکت وابسته", "transaction_date": "2026-09-18", "amount": 1000},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["rpt_id"] == 1

    resp2 = await client.post(
        "/funds/v2/compliance/tse:آگاس/prospectus",
        json={"version": "v2", "change_type": "FEE"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["version"] == "v2"

    resp3 = await client.post(
        "/funds/v2/compliance/tse:آگاس/lifecycle",
        json={"event_type": "RENEWAL", "event_date": "2026-09-18"},
    )
    assert resp3.status_code == 200


async def test_csdi_import_and_reconcile(client: AsyncClient) -> None:
    resp = await client.post(
        "/funds/v2/compliance/tse:آگاس/csdi/statements",
        json={"as_of_date": "2026-09-18", "units_outstanding": 1005, "source_ref": "csdi-1"},
    )
    assert resp.status_code == 200

    resp2 = await client.post("/funds/v2/compliance/tse:آگاس/csdi/reconcile")
    assert resp2.status_code == 200
    data = resp2.json()["data"]
    assert data["status"] == "BREACH"
    assert data["units_diff"] == 5
    assert data["break_id"] == 7


async def test_tax_endpoints(client: AsyncClient) -> None:
    rules = await client.get("/funds/v2/compliance/tax/rules")
    assert rules.status_code == 200
    assert rules.json()["data"]["rules"][0]["tax_type"] == "TRANSFER_05"

    calc = await client.post(
        "/funds/v2/compliance/tse:آگاس/tax/calculate",
        json={"tax_type": "TRANSFER_05", "base_amount": 1_000_000_000, "period_label": "1405-06"},
    )
    assert calc.status_code == 200
    assert calc.json()["data"]["tax_amount"] == 5_000_000

    summary = await client.get("/funds/v2/compliance/tse:آگاس/tax/summary")
    assert summary.status_code == 200
    assert summary.json()["data"]["total_tax"] == 5_000_000


async def test_tax_from_trades_contract(client: AsyncClient) -> None:
    resp = await client.post(
        "/funds/v2/compliance/tse:آگاس/tax/from-trades",
        json={
            "period_label": "1405-06",
            "trades": [
                {"side": "BUY", "value": 1_000_000},
                {"side": "SELL", "value": 2_000_000},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["tax_type"] == "TRANSFER_05"
    assert data["tax_amount"] == 15_000
    assert data["trade_count"] == 2


async def test_governance_endpoints(client: AsyncClient) -> None:
    resp = await client.post(
        "/funds/v2/compliance/tse:آگاس/committees",
        json={"committee_type": "AUDIT", "members": [{"name": "عضو مستقل"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["committee_id"] == 1

    resp2 = await client.post(
        "/funds/v2/compliance/tse:آگاس/internal-audits",
        json={"period_label": "1405-Q2"},
    )
    assert resp2.status_code == 200

    resp3 = await client.post(
        "/funds/v2/compliance/tse:آگاس/disciplinary",
        json={"subject_role": "MANAGER", "case_type": "LATE_DISCLOSURE"},
    )
    assert resp3.status_code == 200

    resp4 = await client.post(
        "/funds/v2/compliance/tse:آگاس/insurance",
        json={"policy_type": "D_AND_O", "coverage_amount": 100_000_000_000},
    )
    assert resp4.status_code == 200


async def test_str_export_contract(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/compliance/tse:آگاس/aml/str/1/export")
    assert resp.status_code == 200
    assert resp.json()["data"]["format"] == "FIU-STR-JSON"
