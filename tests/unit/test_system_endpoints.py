"""End-to-end tests for /api/v1/system/* endpoints (سند §15.3 + §19.3).

These tests use the FastAPI TestClient with auth overrides so the
admin / trader / quant role flows exercise the real router. The
kill-switch state is reset before each test to keep the singleton
clean across runs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.ime_signal_factory import (
    MarketState,
    PricingCandidate,
    StrategyType,
    process_candidate,
)
from services.kill_switch import KillSwitch, TradingHaltedError


def _reset_ks():
    KillSwitch.reset_singleton()
    from services import kill_switch as ks

    ks._LOCAL_STATE.update({"killed": False, "by": "", "reason": "", "at": 0.0})


def _admin_user() -> dict:
    return {"sub": "admin-1", "user_id": "admin-1", "roles": ["admin"]}


def _trader_user() -> dict:
    return {"sub": "trader-1", "user_id": "trader-1", "roles": ["trader"]}


def _quant_user() -> dict:
    return {"sub": "quant-1", "user_id": "quant-1", "roles": ["quant"]}


def _admin_plus_quant_user() -> dict:
    return {"sub": "dual-1", "user_id": "dual-1", "roles": ["admin", "quant"]}


def _client_with_user(user: dict | None) -> TestClient:
    """Build a TestClient with the auth dependency overridden."""
    from apps.api.app import create_app
    from apps.api.dependencies import get_current_user

    app = create_app()
    if user is None:
        # Anonymous → 401 path
        app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(PermissionError("no auth"))
    else:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_ks():
    _reset_ks()
    yield
    _reset_ks()


class TestKillSwitchEndpoints:
    def test_get_state_default(self):
        client = _client_with_user(_admin_user())
        r = client.get("/api/v1/system/kill-switch")
        assert r.status_code == 200
        body = r.json()
        assert body["killed"] is False
        assert body["by"] == ""
        assert body["viewer_roles"] == ["admin"]

    def test_activate_as_admin(self):
        client = _client_with_user(_admin_user())
        r = client.post(
            "/api/v1/system/kill-switch/activate",
            json={"reason": "test halt"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["killed"] is True
        assert body["by"] == "user:admin-1"
        assert body["reason"] == "test halt"

    def test_activate_forbidden_for_trader(self):
        client = _client_with_user(_trader_user())
        r = client.post(
            "/api/v1/system/kill-switch/activate",
            json={"reason": "test halt"},
        )
        assert r.status_code == 403
        assert "admin" in r.json()["detail"].lower()

    def test_activate_forbidden_for_quant(self):
        client = _client_with_user(_quant_user())
        r = client.post(
            "/api/v1/system/kill-switch/activate",
            json={"reason": "test halt"},
        )
        assert r.status_code == 403

    def test_revive_requires_two_distinct_approvers(self):
        client = _client_with_user(_admin_user())
        # Activate first
        r = client.post(
            "/api/v1/system/kill-switch/activate",
            json={"reason": "test halt"},
        )
        assert r.status_code == 200
        # Try to revive with only one role
        r = client.post(
            "/api/v1/system/kill-switch/revive",
            json={"approver_roles": ["admin"]},
        )
        assert r.status_code == 403
        assert "≥2 distinct" in r.json()["detail"]

    def test_revive_with_admin_and_quant(self):
        client = _client_with_user(_admin_plus_quant_user())
        # Activate
        r = client.post(
            "/api/v1/system/kill-switch/activate",
            json={"reason": "test halt"},
        )
        assert r.status_code == 200
        # Revive with admin+quant — distinct roles, no single role has
        # both kill_switch:revive AND model:write
        r = client.post(
            "/api/v1/system/kill-switch/revive",
            json={"approver_roles": ["admin", "quant"]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["killed"] is False
        assert body["approver_roles"] == ["admin", "quant"]

    def test_revive_missing_approver_list(self):
        client = _client_with_user(_admin_user())
        r = client.post("/api/v1/system/kill-switch/revive", json={})
        assert r.status_code == 422


class TestPermissionCheck:
    def test_admin_sees_kill_switch(self):
        client = _client_with_user(_admin_user())
        r = client.get("/api/v1/system/permissions/check?permission=kill_switch:activate")
        assert r.status_code == 200
        body = r.json()
        assert body["granted"] is True
        assert "admin" in body["granted_by_roles"]

    def test_trader_does_not_have_kill_switch(self):
        client = _client_with_user(_trader_user())
        r = client.get("/api/v1/system/permissions/check?permission=kill_switch:activate")
        assert r.status_code == 200
        body = r.json()
        assert body["granted"] is False
        assert body["granted_by_roles"] == []

    def test_quant_has_model_write_but_not_risk_write(self):
        client = _client_with_user(_quant_user())
        r_model = client.get("/api/v1/system/permissions/check?permission=model:write")
        assert r_model.json()["granted"] is True
        r_risk = client.get("/api/v1/system/permissions/check?permission=risk:write")
        assert r_risk.json()["granted"] is False


class TestSignalFactoryIntegration:
    """سند §15.3 step 2: in-process signal factory also halts when the
    kill switch is engaged, not just the HTTP layer."""

    def _passing_candidate(self) -> PricingCandidate:
        return PricingCandidate(
            candidate_id="t",
            strategy_type=StrategyType.CALENDAR_ARB,
            instrument_keys=["a"],
            theoretical_price=100.0,
            market_price=99.0,
            mispricing_pct=0.01,
            iv=0.3,
            data_quality=0.9,
            liquidity_depth=0.8,
            execution_ease=0.85,
            model_confidence=0.75,
        )

    def _passing_state(self) -> MarketState:
        return MarketState(
            snapshot_age_seconds=2.0,
            days_to_delivery=10.0,
            visible_volume=1000,
            min_strategy_volume=200,
            tick_size=1.0,
            proposed_price=100.0,
            gross_edge=1000.0,
            commission=10.0,
            market_impact=0.0,
            latency_buffer=5.0,
            avg_volume=5000,
            short_term_volatility=0.2,
            eta=0.1,
            gamma=0.05,
            account_risk_budget=10_000.0,
            stop_loss_distance=10.0,
        )

    async def test_activate_endpoint_halts_factory(self):
        from services.kill_switch import kill_switch

        client = _client_with_user(_admin_user())
        r = client.post(
            "/api/v1/system/kill-switch/activate",
            json={"reason": "halt for test"},
        )
        assert r.status_code == 200
        # Process candidate via the in-process factory should now raise
        assert kill_switch.is_killed() is True
        with pytest.raises(TradingHaltedError):
            process_candidate(self._passing_candidate(), self._passing_state())
