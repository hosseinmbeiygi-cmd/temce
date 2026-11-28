"""Regression tests for audit finding F3 — failed delivery must not arm the cooldown
(ممیزی 2026-11-28).

Fixed: ``evaluate_and_trigger`` now calls ``_deliver_by_channel`` directly and arms
``last_triggered`` only when no channel reported "failed" — a failed transport no
longer suppresses the next pass, and the 2-minute job cadence acts as the retry.
not_configured/skipped still arm the cooldown (no transport can ever deliver them).

If the first test fails again, the cooldown is being armed on failed sends (regression
of F3); the second test pins behaviour that must survive any future fix.
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


def _fake_alert() -> MagicMock:
    alert = MagicMock()
    alert.id = "alr_delivery"
    alert.user_id = "usr_demo"
    alert.symbol = "فولاد"
    alert.instrument_id = ""
    alert.enabled = True
    alert.condition = json.dumps({"field": "price", "operator": "gte",
                                  "threshold": 5000.0, "cooldown_minutes": 30})
    alert.channels = json.dumps(["telegram"])
    alert.triggered_count = 0
    alert.last_triggered = None
    return alert


@pytest.mark.asyncio
async def test_failed_delivery_must_not_arm_cooldown():
    alert = _fake_alert()
    svc = AlertService(_mock_session([alert]))
    delivery = AsyncMock(side_effect=[{"telegram": "failed"}, {"telegram": "delivered"}])
    with patch.object(svc, "_deliver_by_channel", delivery):
        first = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
        assert len(first) == 1                      # condition did hold
        assert first[0]["delivered"] is False       # honest outcome in the trigger report
        assert alert.last_triggered is None         # failure must NOT arm the cooldown

        second = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
        assert len(second) == 1                     # retried on the next pass and delivered
        assert second[0]["delivered"] is True


@pytest.mark.asyncio
async def test_successful_delivery_arms_cooldown():
    """Pinned behaviour: after a successful delivery, consecutive passes inside the
    cooldown window must not re-notify."""
    alert = _fake_alert()
    svc = AlertService(_mock_session([alert]))
    with patch.object(svc, "_deliver_by_channel",
                      AsyncMock(return_value={"telegram": "delivered"})):
        first = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
        second = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
    assert len(first) == 1
    assert len(second) == 0
    assert alert.triggered_count == 1


@pytest.mark.asyncio
async def test_not_configured_channels_still_arm_cooldown():
    """Console-only alerts can never be 'delivered'; the trigger must still be
    recorded once per cooldown window instead of on every pass."""
    alert = MagicMock()
    alert.id = "alr_console"
    alert.user_id = "usr_demo"
    alert.symbol = "فولاد"
    alert.instrument_id = ""
    alert.enabled = True
    alert.condition = json.dumps({"field": "price", "operator": "gte",
                                  "threshold": 5000.0, "cooldown_minutes": 30})
    alert.channels = json.dumps(["console"])
    alert.triggered_count = 0
    alert.last_triggered = None
    svc = AlertService(_mock_session([alert]))
    with patch.object(svc, "_deliver_by_channel",
                      AsyncMock(return_value={"console": "not_configured"})):
        first = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
        second = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
    assert len(first) == 1
    assert len(second) == 0
