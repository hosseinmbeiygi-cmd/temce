"""تست‌های API صندوق‌یار — happy path + error path برای هر endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.funds.api import router as funds_router
from apps.funds.auth import issue_token

app = FastAPI()
app.include_router(funds_router)

client = TestClient(app)


def test_list_funds_happy_path():
    resp = client.get("/funds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 5
    assert body["disclaimer"]  # شرط spec: disclaimer در بدنه هر پاسخ
    assert body["items"][0]["type_label_fa"]


def test_fund_profile_happy_path():
    resp = client.get("/funds/اهرم")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "اهرم"
    assert body["recommendation"]["signal"] in ("strong_buy", "buy", "hold", "caution", "avoid")
    assert body["recommendation"]["disclaimer"]
    # Reason Vector
    assert len(body["recommendation"]["reasons"]) >= 1


def test_fund_profile_not_found():
    resp = client.get("/funds/ناموجود")
    assert resp.status_code == 404


def test_compare_happy_path():
    resp = client.get("/funds/compare", params={"symbols": "طلا,عیار"})
    assert resp.status_code == 200
    assert len(resp.json()["funds"]) == 2


def test_compare_invalid_count():
    resp = client.get("/funds/compare", params={"symbols": "طلا"})
    assert resp.status_code == 400


def test_screener_requires_analyst():
    """screener فقط برای analyst/admin (شرط spec: RBAC)."""
    resp = client.post("/funds/screener", json={"type_code": "GO"})
    assert resp.status_code == 403  # guest بدون توکن


def test_screener_with_analyst_token():
    token = issue_token("analyst-1", "analyst")
    resp = client.post(
        "/funds/screener",
        json={"type_code": "GO", "filters": [{"field": "p_nav_ratio", "op": "gt", "value": 0}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 2  # طلا و عیار


def test_backtest_requires_analyst():
    resp = client.get("/funds/backtest/report")
    assert resp.status_code == 403


def test_bubble_live():
    resp = client.get("/funds/bubble/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"]
    assert all("bubble_pct" in i for i in body["items"])


def test_health_sources():
    resp = client.get("/funds/health/sources")
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()["sources"]}
    assert {"fipiran", "tsetmc"} <= names


def test_invalid_type_code():
    resp = client.get("/funds", params={"type_code": "ZZ"})
    assert resp.status_code == 400


def test_api_key_auth():
    """API key → نقش analyst (دسترسی screener)."""
    resp = client.post(
        "/funds/screener",
        json={"type_code": "GO"},
        headers={"X-API-Key": "syar_dev_" + "a" * 32},
    )
    assert resp.status_code == 200
