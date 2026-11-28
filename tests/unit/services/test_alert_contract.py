"""Regression tests for audit finding F1 — alert condition contract (ممیزی 2026-11-28).

Fixed: ``AlertService`` now validates ``condition`` on create/update
(``validate_condition``) and applies a server-side default cooldown
(``DEFAULT_COOLDOWN_MINUTES``) when a condition omits the key, so an alert created
outside the UI no longer re-triggers on every 2-minute pass.

If these tests fail, the write-time validation or the default cooldown regressed.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.alert_service import AlertService


def _mock_session(alerts: list[MagicMock]) -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = alerts
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    return session


def _fake_alert(condition: dict) -> MagicMock:
    alert = MagicMock()
    alert.id = "alr_contract"
    alert.user_id = "usr_demo"
    alert.symbol = "فولاد"
    alert.instrument_id = ""
    alert.enabled = True
    alert.condition = json.dumps(condition)
    alert.channels = json.dumps(["telegram"])
    alert.triggered_count = 0
    alert.last_triggered = None
    return alert


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_condition",
    [
        {"field": "price", "operator": "gtt", "threshold": 100},  # unknown operator
        {"field": "price", "operator": "gte", "threshold": "abc"},  # non-numeric threshold
        {"field": "no_such_field", "operator": "gte", "threshold": 1},  # unknown field
    ],
    ids=["bad_operator", "bad_threshold", "bad_field"],
)
async def test_create_alert_rejects_invalid_condition(bad_condition):
    """create_alert must refuse a condition it could never evaluate correctly."""
    svc = AlertService(_mock_session([]))
    result = await svc.create_alert(
        user_id="usr_demo", instrument_id="", symbol="فولاد",
        alert_type="price_above", condition=bad_condition,
        channels=["telegram"], description="",
    )
    assert not result.success


@pytest.mark.asyncio
async def test_update_alert_rejects_invalid_condition():
    svc = AlertService(_mock_session([]))
    result = await svc.update_alert("alr_contract", "usr_demo",
                                    condition={"operator": "gtt", "threshold": 1})
    assert not result.success


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "null_condition",
    [
        {"field": "price", "operator": "gte", "threshold": None},  # JSON.stringify(NaN) → null
        {"field": "price", "operator": None, "threshold": 100},
        {"field": None, "operator": "gte", "threshold": 100},
        {"field": "price", "operator": "gte", "threshold": 100, "cooldown_minutes": None},
    ],
    ids=["null_threshold", "null_operator", "null_field", "null_cooldown"],
)
async def test_create_alert_rejects_null_values(null_condition):
    """A key present with null is invalid — that is how a NaN threshold reaches the
    API through JSON.stringify; it used to pass validation and die silently later."""
    svc = AlertService(_mock_session([]))
    result = await svc.create_alert(
        user_id="usr_demo", instrument_id="", symbol="فولاد",
        alert_type="price_above", condition=null_condition,
        channels=["telegram"], description="",
    )
    assert not result.success


@pytest.mark.asyncio
async def test_create_alert_still_accepts_empty_condition():
    """The free-form ``{}`` condition (used by existing rows/tests) stays valid —
    validation only checks the keys the evaluator reads."""
    svc = AlertService(_mock_session([]))
    result = await svc.create_alert(
        user_id="usr_demo", instrument_id="", symbol="فولاد",
        alert_type="price_above", condition={},
        channels=["telegram"], description="",
    )
    assert result.success


@pytest.mark.asyncio
async def test_missing_cooldown_gets_server_default():
    """A condition without cooldown_minutes must get the server default, so
    API-created alerts cannot spam a notification on every 2-minute pass."""
    alert = _fake_alert({"field": "price", "operator": "gte", "threshold": 5000.0})
    svc = AlertService(_mock_session([alert]))
    with patch.object(svc, "_deliver_by_channel",
                      AsyncMock(return_value={"telegram": "delivered"})):
        first = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
        second = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
    assert len(first) == 1
    assert len(second) == 0, "second consecutive pass must be suppressed by the default cooldown"


@pytest.mark.asyncio
async def test_explicit_zero_cooldown_is_respected():
    """An explicit cooldown_minutes=0 keeps the caller's opt-out behaviour."""
    alert = _fake_alert({"field": "price", "operator": "gte", "threshold": 5000.0,
                         "cooldown_minutes": 0})
    svc = AlertService(_mock_session([alert]))
    with patch.object(svc, "_deliver_by_channel",
                      AsyncMock(return_value={"telegram": "delivered"})):
        first = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
        second = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
    assert len(first) == 1
    assert len(second) == 1
