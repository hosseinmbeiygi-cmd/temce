"""Contract tests for /funds/v2/nav/* endpoints (no DB required).

سرویس‌ها با dependency_overrides جایگزین می‌شوند تا فقط «قرارداد مسیر و پاسخ»
قفل شود: پوشش envelope، کد وضعیت، و نگاشت خطاها (400/404).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from apps.api.endpoints.funds_nav import _get_class_nav, _get_engine, _get_fof, _get_recon  # noqa: E402
from apps.api.endpoints.funds_nav import router as funds_nav_router  # noqa: E402
from services.fund_read_through import StaleResult  # noqa: E402

_RUN = {
    "run_id": 7,
    "fund_id": "tse:آگاس",
    "valuation_date": "2026-09-18",
    "nav_type": "STATISTICAL",
    "quality_status": "ESTIMATED",
    "coverage_pct": 82.5,
    "nav_per_unit": 12_345.0,
    "net_assets": 1_234_500_000.0,
    "positions": [],
}


def _fake_engine() -> Any:
    engine = MagicMock()
    engine.calculate = AsyncMock(
        return_value=StaleResult(data=dict(_RUN), freshness="estimated", fetched_from="db")
    )
    engine.get_latest = AsyncMock(return_value=dict(_RUN))
    engine.list_runs = AsyncMock(return_value=[dict(_RUN)])
    engine.get_run = AsyncMock(return_value=dict(_RUN))
    engine.backfill = AsyncMock(
        return_value=StaleResult(
            data={"fund_id": "tse:آگاس", "requested": 30, "created": 25, "skipped": 5, "failed": 0},
            freshness="estimated",
        )
    )
    return engine


def _fake_class_nav() -> Any:
    svc = MagicMock()
    svc.get_latest = AsyncMock(
        return_value={
            "fund_id": "tse:آگاس",
            "valuation_date": "2026-09-18",
            "allocation_type": "LEVERAGED",
            "classes": [
                {"class_code": "ORDINARY", "net_assets": 130_000, "units": 100, "nav_per_unit": 1300},
                {"class_code": "PREFERRED", "net_assets": 90_000, "units": 100, "nav_per_unit": 900},
            ],
        }
    )
    svc.set_class_config = AsyncMock(
        return_value=[{"class_code": "ORDINARY", "version": "v1", "id": 1}]
    )
    svc.calculate = AsyncMock(
        return_value=StaleResult(
            data={
                "fund_id": "tse:آگاس",
                "allocation_type": "LEVERAGED",
                "classes": {"ORDINARY": {"nav_per_unit": 1300}, "PREFERRED": {"nav_per_unit": 900}},
                "warnings": [],
            },
            freshness="estimated",
        )
    )
    return svc


def _fake_recon() -> Any:
    recon = MagicMock()
    recon.reconcile = AsyncMock(
        return_value=StaleResult(
            data={
                "recon_run_id": 3,
                "fund_id": "tse:آگاس",
                "comparability_status": "COMPARABLE",
                "reference_status": "VALID",
                "diff_status": "MATCHED",
                "internal_nav": 12_345.0,
                "reference_nav": 12_350.0,
                "abs_diff": -5.0,
                "bps_diff": -4.05,
                "break_id": None,
            },
            freshness="live",
            fetched_from="db",
        )
    )
    recon.list_reconciliations = AsyncMock(return_value=[])
    recon.list_breaks = AsyncMock(return_value=[])
    recon.update_break = AsyncMock(
        return_value={"break_id": 1, "lifecycle": "INVESTIGATING"}
    )
    recon.calibrate_thresholds = AsyncMock(
        return_value={
            "fund_id": "tse:آگاس",
            "nav_type": "STATISTICAL",
            "sample_size": 42,
            "abs_warn": 1_500_000,
            "abs_breach": 4_000_000,
            "bps_warn": 12.0,
            "bps_breach": 55.0,
            "version": "cal-1",
        }
    )
    recon.shadow_acceptance = AsyncMock(
        return_value={
            "fund_id": "tse:آگاس",
            "summary": {"days": 21, "match_rate": 1.0, "acceptance_ready": True},
            "rows": [],
            "engine_version": "nav-recon-1.0.0",
        }
    )
    return recon


def _fake_fof() -> Any:
    svc = MagicMock()
    svc.get_latest = AsyncMock(
        return_value={
            "fund_id": "tse:آگاس",
            "valuation_date": "2026-09-18",
            "positions": [],
            "summary": {"total_value": 100_000_000, "coverage_pct": 100.0},
        }
    )
    svc.calculate = AsyncMock(
        return_value=StaleResult(
            data={
                "fund_id": "tse:آگاس",
                "summary": {"total_value": 100_000_000, "coverage_pct": 100.0},
                "cycles": [],
                "quality": "COMPLETE",
            },
            freshness="estimated",
        )
    )
    return svc


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(funds_nav_router, prefix="/funds/v2/nav")
    application.dependency_overrides[_get_engine] = _fake_engine
    application.dependency_overrides[_get_recon] = _fake_recon
    application.dependency_overrides[_get_class_nav] = _fake_class_nav
    application.dependency_overrides[_get_fof] = _fake_fof
    return application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_calculate_returns_envelope(client: AsyncClient) -> None:
    resp = await client.post("/funds/v2/nav/tse:آگاس/calculate", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["run_id"] == 7
    assert body["data"]["nav_per_unit"] == 12_345.0
    assert "freshness" in body


async def test_calculate_rejects_invalid_nav_type(client: AsyncClient) -> None:
    resp = await client.post(
        "/funds/v2/nav/tse:آگاس/calculate", json={"nav_type": "WRONG"}
    )
    assert resp.status_code == 400


async def test_latest_returns_run(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/nav/tse:آگاس/latest")
    assert resp.status_code == 200
    assert resp.json()["data"]["run_id"] == 7


async def test_runs_and_run_detail(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/nav/tse:آگاس/runs?limit=5")
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 1

    resp2 = await client.get("/funds/v2/nav/tse:آگاس/runs/7")
    assert resp2.status_code == 200
    assert resp2.json()["data"]["run_id"] == 7


async def test_reconcile_returns_three_dimensions(client: AsyncClient) -> None:
    resp = await client.post("/funds/v2/nav/tse:آگاس/reconcile", json={})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["comparability_status"] == "COMPARABLE"
    assert data["reference_status"] == "VALID"
    assert data["diff_status"] == "MATCHED"


async def test_dashboard_bundle(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/nav/tse:آگاس/dashboard")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fund_id"] == "tse:آگاس"
    assert data["latest_run"]["run_id"] == 7
    assert "open_breaks" in data


async def test_breaks_list_and_update(app: FastAPI, client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/nav/breaks")
    assert resp.status_code == 200
    assert resp.json()["data"]["breaks"] == []

    resp2 = await client.patch(
        "/funds/v2/nav/breaks/1",
        json={"lifecycle": "INVESTIGATING", "notes": "بررسی قیمت"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["lifecycle"] == "INVESTIGATING"


async def test_update_break_invalid_transition_maps_to_400(
    app: FastAPI, client: AsyncClient
) -> None:
    bad = MagicMock()
    bad.update_break = AsyncMock(side_effect=ValueError("گذار نامعتبر"))
    app.dependency_overrides[_get_recon] = lambda: bad
    resp = await client.patch("/funds/v2/nav/breaks/1", json={"lifecycle": "OPEN"})
    assert resp.status_code == 400


async def test_break_update_uses_operator_header_as_owner(
    app: FastAPI, client: AsyncClient
) -> None:
    captured: dict = {}

    async def fake_update(break_id, lifecycle, notes=None, owner=None):
        captured.update(owner=owner)
        return {"break_id": break_id, "lifecycle": lifecycle}

    recon = MagicMock()
    recon.update_break = AsyncMock(side_effect=fake_update)
    app.dependency_overrides[_get_recon] = lambda: recon
    resp = await client.patch(
        "/funds/v2/nav/breaks/1",
        json={"lifecycle": "INVESTIGATING"},
        headers={"X-Operator": "op-42"},
    )
    assert resp.status_code == 200
    assert captured["owner"] == "op-42"


async def test_run_detail_not_found_maps_to_404(
    app: FastAPI, client: AsyncClient
) -> None:
    engine = MagicMock()
    engine.get_run = AsyncMock(return_value=None)
    app.dependency_overrides[_get_engine] = lambda: engine
    resp = await client.get("/funds/v2/nav/tse:آگاس/runs/999")
    assert resp.status_code == 404


async def test_evidence_pack_includes_integrity_hash(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/nav/tse:آگاس/evidence")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["fund_id"] == "tse:آگاس"
    assert isinstance(data["integrity_hash"], str)
    assert len(data["integrity_hash"]) == 64
    assert "breaks" in data
    assert "latest_run" in data


async def test_class_nav_latest_and_calculate(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/nav/tse:آگاس/class-nav")
    assert resp.status_code == 200
    assert resp.json()["data"]["allocation_type"] == "LEVERAGED"

    resp2 = await client.post("/funds/v2/nav/tse:آگاس/class-nav/calculate", json={})
    assert resp2.status_code == 200
    assert "classes" in resp2.json()["data"]


async def test_class_nav_config_validation(client: AsyncClient) -> None:
    resp = await client.put(
        "/funds/v2/nav/tse:آگاس/class-nav/config",
        json={"version": "v1", "classes": [{"class_code": "ORDINARY", "allocation_type": "WRONG"}]},
    )
    assert resp.status_code == 400

    resp2 = await client.put(
        "/funds/v2/nav/tse:آگاس/class-nav/config",
        json={"version": "v1", "classes": [{"class_code": "ORDINARY", "allocation_type": "SIMPLE"}]},
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["saved"][0]["version"] == "v1"


async def test_backfill_and_calibration(client: AsyncClient) -> None:
    resp = await client.post("/funds/v2/nav/tse:آگاس/backfill", json={"days": 30})
    assert resp.status_code == 200
    assert resp.json()["data"]["created"] == 25

    resp2 = await client.post(
        "/funds/v2/nav/tse:آگاس/thresholds/calibrate", json={"min_samples": 10}
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["version"] == "cal-1"


async def test_fof_latest_and_calculate(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/nav/tse:آگاس/fof")
    assert resp.status_code == 200
    assert resp.json()["data"]["summary"]["coverage_pct"] == 100.0

    resp2 = await client.post("/funds/v2/nav/tse:آگاس/fof/calculate", json={})
    assert resp2.status_code == 200
    assert resp2.json()["data"]["quality"] == "COMPLETE"


async def test_shadow_acceptance_contract(client: AsyncClient) -> None:
    resp = await client.get("/funds/v2/nav/tse:آگاس/shadow-acceptance?days=30")
    assert resp.status_code == 200
    summary = resp.json()["data"]["summary"]
    assert summary["acceptance_ready"] is True
    assert summary["days"] == 21
