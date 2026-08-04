"""Unit tests for AlertService.

Covers:
  - list_alerts: paginated alert listing
  - create_alert: new alert creation
  - update_alert: updating existing alerts
  - delete_alert: removing alerts
  - get_alert_history: history of triggered alerts
  - evaluate_and_trigger: condition evaluation and triggering
  - _deliver_notification: multi-channel delivery
  - _alert_to_dict: entity → dict conversion
  - Edge cases and error handling
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.result import Result
from services.alert_service import AlertService

# ── Helpers ──────────────────────────────────────────────────────


def _make_service(**kwargs: Any) -> AlertService:
    """Create an AlertService with mocked session."""
    defaults: dict[str, Any] = {"session": AsyncMock()}
    defaults.update(kwargs)
    return AlertService(**defaults)


def _make_alert_model(**overrides: Any) -> MagicMock:
    """Create a mock AlertModel with default values."""
    defaults = {
        "id": "alr_001",
        "instrument_id": "inst_001",
        "symbol": "فولاد",
        "alert_type": "price_above",
        "condition": json.dumps({"field": "price_last", "operator": "gte", "threshold": 5000}),
        "channels": json.dumps(["console", "sound"]),
        "enabled": True,
        "description": "قیمت بالای ۵۰۰۰",
        "triggered_count": 0,
        "last_triggered": None,
        "created_at": datetime(2024, 1, 15, 10, 0, 0),
        "updated_at": datetime(2024, 1, 15, 10, 0, 0),
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


def _make_alert_history_model(**overrides: Any) -> MagicMock:
    """Create a mock AlertHistoryModel with default values."""
    defaults = {
        "id": "alh_001",
        "alert_id": "alr_001",
        "triggered_at": datetime(2024, 1, 15, 11, 0, 0),
        "trigger_value": 5000.0,
        "message": "فولاد price_last reached 5000",
        "delivered": True,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


# ════════════════════════════════════════════════════════════════
# 1. list_alerts
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestListAlerts:
    async def test_returns_paginated_alerts(self):
        svc = _make_service()
        alerts = [_make_alert_model(), _make_alert_model(id="alr_002")]

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = alerts
            return result

        async def mock_scalar(stmt):
            return 2

        # Patch select to prevent SQL construction errors in list_alerts
        # The real list_alerts() calls select(AlertModel), which would fail
        # eagerly against Mock session. Instead, mock select to return a chain.
        mock_select = MagicMock()
        mock_select.return_value.order_by.return_value.offset.return_value.limit.return_value = MagicMock()
        with patch("services.alert_service.select", mock_select):
            svc.session.execute = mock_execute
            svc.session.scalar = mock_scalar
            result = await svc.list_alerts()

        assert result.success
        assert result.value["total"] == 2
        assert len(result.value["items"]) == 2

    async def test_empty_list(self):
        svc = _make_service()

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            return result

        async def mock_scalar(stmt):
            return 0

        mock_select = MagicMock()
        mock_select.return_value.order_by.return_value.offset.return_value.limit.return_value = MagicMock()
        with patch("services.alert_service.select", mock_select):
            svc.session.execute = mock_execute
            svc.session.scalar = mock_scalar
            result = await svc.list_alerts()

        assert result.success
        assert result.value["total"] == 0

    async def test_repo_failure(self):
        svc = _make_service()
        svc.session.execute = AsyncMock(side_effect=Exception("DB error"))

        result = await svc.list_alerts()
        assert not result.success
        assert "DB error" in result.error

    async def test_pagination_params(self):
        svc = _make_service()

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            return result

        async def mock_scalar(stmt):
            return 100

        mock_select = MagicMock()
        mock_select.return_value.order_by.return_value.offset.return_value.limit.return_value = MagicMock()
        with patch("services.alert_service.select", mock_select):
            svc.session.execute = mock_execute
            svc.session.scalar = mock_scalar
            result = await svc.list_alerts(page=3, page_size=10)

        assert result.success
        assert result.value["page"] == 3
        assert result.value["page_size"] == 10


# ════════════════════════════════════════════════════════════════
# 2. create_alert
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestCreateAlert:
    async def test_creates_alert(self):
        svc = _make_service()
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        result = await svc.create_alert(
            user_id="user_001",
            instrument_id="inst_001",
            symbol="فولاد",
            alert_type="price_above",
            condition={"field": "price_last", "operator": "gte", "threshold": 5000},
            channels=["console", "sound"],
            description="قیمت بالای ۵۰۰۰",
        )
        assert result.success
        svc.session.add.assert_called_once()
        svc.session.flush.assert_called_once()

    async def test_create_generates_id(self):
        svc = _make_service()
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        result = await svc.create_alert(
            user_id="user_001",
            instrument_id="inst_001",
            symbol="فولاد",
            alert_type="price_above",
            condition={},
            channels=[],
            description="",
        )
        assert result.success
        call_args = svc.session.add.call_args
        alert = call_args[0][0]
        assert alert.id.startswith("alr_")

    async def test_create_failure(self):
        svc = _make_service()
        svc.session.add = MagicMock(side_effect=Exception("Constraint violation"))

        result = await svc.create_alert(
            user_id="user_001",
            instrument_id="inst_001",
            symbol="فولاد",
            alert_type="price_above",
            condition={},
            channels=[],
            description="",
        )
        assert not result.success
        assert "Constraint violation" in result.error


# ════════════════════════════════════════════════════════════════
# 3. update_alert
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestUpdateAlert:
    async def test_updates_existing_alert(self):
        svc = _make_service()
        alert = _make_alert_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = alert
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.flush = AsyncMock()

        result = await svc.update_alert("alr_001", "user_001", description="توضیحات جدید")
        assert result.success
        assert alert.description == "توضیحات جدید"

    async def test_updates_condition(self):
        svc = _make_service()
        alert = _make_alert_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = alert
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.flush = AsyncMock()

        new_condition = {"field": "price_last", "operator": "lte", "threshold": 4000}
        result = await svc.update_alert("alr_001", "user_001", condition=new_condition)
        assert result.success
        assert json.loads(alert.condition) == new_condition

    async def test_updates_channels(self):
        svc = _make_service()
        alert = _make_alert_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = alert
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.flush = AsyncMock()

        new_channels = ["email"]
        result = await svc.update_alert("alr_001", "user_001", channels=new_channels)
        assert result.success
        assert json.loads(alert.channels) == ["email"]

    async def test_updates_enabled(self):
        svc = _make_service()
        alert = _make_alert_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = alert
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.flush = AsyncMock()

        result = await svc.update_alert("alr_001", "user_001", enabled=False)
        assert result.success
        assert alert.enabled is False

    async def test_not_found(self):
        svc = _make_service()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        svc.session.execute = AsyncMock(return_value=mock_result)

        result = await svc.update_alert("alr_999", "user_001", description="test")
        assert not result.success
        assert "not found" in result.error.lower()


# ════════════════════════════════════════════════════════════════
# 4. delete_alert
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestDeleteAlert:
    async def test_deletes_existing_alert(self):
        svc = _make_service()
        alert = _make_alert_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = alert
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.delete = AsyncMock()
        svc.session.flush = AsyncMock()

        result = await svc.delete_alert("alr_001", "user_001")
        assert result.success
        svc.session.delete.assert_called_once_with(alert)

    async def test_not_found(self):
        svc = _make_service()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        svc.session.execute = AsyncMock(return_value=mock_result)

        result = await svc.delete_alert("alr_999", "user_001")
        assert not result.success
        assert "not found" in result.error.lower()


# ════════════════════════════════════════════════════════════════
# 5. get_alert_history
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetAlertHistory:
    async def test_returns_history(self):
        svc = _make_service()
        history = [_make_alert_history_model(), _make_alert_history_model(id="alh_002")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = history

        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.scalar = AsyncMock(return_value=2)  # count query

        result = await svc.get_alert_history("alr_001")
        assert result.success
        assert result.value["total"] == 2
        assert len(result.value["items"]) == 2

    async def test_empty_history(self):
        svc = _make_service()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.scalar = AsyncMock(return_value=0)

        result = await svc.get_alert_history("alr_001")
        assert result.success
        assert result.value["total"] == 0

    async def test_repo_failure(self):
        svc = _make_service()
        svc.session.execute = AsyncMock(side_effect=Exception("DB error"))

        result = await svc.get_alert_history("alr_001")
        assert not result.success
        assert "DB error" in result.error

    async def test_pagination_includes_page_meta(self):
        svc = _make_service()
        history = [_make_alert_history_model()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = history

        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.scalar = AsyncMock(return_value=1)

        result = await svc.get_alert_history("alr_001", page=2, page_size=10)
        assert result.success
        assert result.value["page"] == 2
        assert result.value["page_size"] == 10


# ════════════════════════════════════════════════════════════════
# 6. evaluate_and_trigger
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEvaluateAndTrigger:
    async def test_triggers_on_threshold(self):
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({"field": "price_last", "operator": "gte", "threshold": 5000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 1
        assert triggered[0]["alert_id"] == "alr_001"
        assert triggered[0]["value"] == 5100

    async def test_does_not_trigger_below_threshold(self):
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({"field": "price_last", "operator": "gte", "threshold": 5000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 4900)
        assert len(triggered) == 0

    async def test_triggers_on_less_than(self):
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({"field": "price_last", "operator": "lt", "threshold": 5000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 4900)
        assert len(triggered) == 1

    async def test_skips_different_field(self):
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({"field": "volume", "operator": "gte", "threshold": 100000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 0

    async def test_skips_disabled_alerts(self):
        svc = _make_service()
        # When enabled=False, the SQLAlchemy query filters it out.
        # Mock returns empty because the filter excludes disabled alerts.
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        svc.session.execute = AsyncMock(return_value=mock_result)

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 0

    async def test_multiple_alerts(self):
        svc = _make_service()
        alert1 = _make_alert_model(
            id="alr_001",
            condition=json.dumps({"field": "price_last", "operator": "gte", "threshold": 5000}),
            channels=json.dumps(["console"]),
        )
        alert2 = _make_alert_model(
            id="alr_002",
            condition=json.dumps({"field": "price_last", "operator": "lte", "threshold": 4000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert1, alert2]
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 1
        assert triggered[0]["alert_id"] == "alr_001"


    async def test_no_match_criteria_returns_empty(self):
        """Both instrument_id and symbol empty → no alerts should be queried."""
        svc = _make_service()
        triggered = await svc.evaluate_and_trigger("", "", "price_last", 5100)
        assert triggered == []
        svc.session.execute.assert_not_called()

    async def test_matches_alert_by_symbol_when_instrument_id_empty(self):
        """Alerts created from the frontend have empty instrument_id.

        The trigger pipeline passes a real instrument_id, so matching must also
        fall back to symbol. The mocked query already returns the alert; the
        point is that evaluation succeeds (i.e. symbol OR instrument match).
        """
        svc = _make_service()
        alert = _make_alert_model(
            instrument_id="",
            condition=json.dumps({"field": "price_last", "operator": "gte", "threshold": 5000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 1

    async def test_normalizes_price_field_names(self):
        """Frontend stores field="price"; pipeline evaluates "price_last".

        Both should normalize to the same canonical field so the alert fires.
        """
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({"field": "price", "operator": "gte", "threshold": 5000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 1

    async def test_neq_operator(self):
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({"field": "price_last", "operator": "neq", "threshold": 5000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 1

        # Same value as threshold → neq should NOT trigger
        alert2 = _make_alert_model(
            id="alr_002",
            condition=json.dumps({"field": "price_last", "operator": "neq", "threshold": 5000}),
            channels=json.dumps(["console"]),
        )
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [alert2]
        svc.session.execute = AsyncMock(return_value=mock_result2)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        triggered2 = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5000)
        assert len(triggered2) == 0

    async def test_cooldown_skips_recently_triggered(self):
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({
                "field": "price_last", "operator": "gte", "threshold": 5000,
                "cooldown_minutes": 30,
            }),
            channels=json.dumps(["console"]),
            last_triggered=datetime(2024, 1, 15, 10, 0, 0),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)

        # "Now" is only a few minutes after last_triggered → within cooldown
        with patch("services.alert_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 10, 5, 0)
            triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 0

    async def test_cooldown_allows_after_window(self):
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({
                "field": "price_last", "operator": "gte", "threshold": 5000,
                "cooldown_minutes": 30,
            }),
            channels=json.dumps(["console"]),
            last_triggered=datetime(2024, 1, 15, 10, 0, 0),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        with patch("services.alert_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 11, 0, 0)
            triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 1

    async def test_unknown_operator_never_triggers(self):
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({"field": "price_last", "operator": "bogus", "threshold": 5000}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5100)
        assert len(triggered) == 0

    async def test_cross_sma_above_triggers_on_cross(self):
        svc = _make_service()
        alert = _make_alert_model(
            condition=json.dumps({"field": "sma_cross_above", "operator": "eq", "threshold": 1}),
            channels=json.dumps(["console"]),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "sma_cross_above", 1.0)
        assert len(triggered) == 1

        # No cross today → 0.0 → should NOT trigger
        alert2 = _make_alert_model(
            id="alr_002",
            condition=json.dumps({"field": "sma_cross_above", "operator": "eq", "threshold": 1}),
            channels=json.dumps(["console"]),
        )
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [alert2]
        svc.session.execute = AsyncMock(return_value=mock_result2)
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        triggered2 = await svc.evaluate_and_trigger("inst_001", "فولاد", "sma_cross_above", 0.0)
        assert len(triggered2) == 0


# ════════════════════════════════════════════════════════════════
# 7. _deliver_notification
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestDeliverNotification:
    async def test_console_channel(self):
        svc = _make_service()
        await svc._deliver_notification("Test message", ["console"])

    async def test_sound_channel(self):
        svc = _make_service()
        await svc._deliver_notification("Test message", ["sound"])

    async def test_email_channel(self):
        svc = _make_service()
        await svc._deliver_notification("Test message", ["email"])

    async def test_multiple_channels(self):
        svc = _make_service()
        await svc._deliver_notification("Test message", ["console", "sound", "email"])

    async def test_unknown_channel(self):
        svc = _make_service()
        await svc._deliver_notification("Test message", ["unknown_channel"])

    async def test_console_channel_returns_true(self):
        svc = _make_service()
        delivered = await svc._deliver_notification("Test message", ["console"])
        assert delivered is True

    async def test_empty_channels_returns_false(self):
        svc = _make_service()
        delivered = await svc._deliver_notification("Test message", [])
        assert delivered is False

    async def test_telegram_channel_uses_telegram_sender(self):
        svc = _make_service()
        with patch("integrations.notifications.telegram_sender.TelegramSender") as MockSender:
            mock_sender = AsyncMock()
            mock_sender.send.return_value = Result.ok(True)
            MockSender.return_value = mock_sender
            delivered = await svc._deliver_notification("Test message", ["telegram"])
        assert delivered is True
        mock_sender.send.assert_awaited_once_with("Test message")


# ════════════════════════════════════════════════════════════════
# 8. _alert_to_dict
# ════════════════════════════════════════════════════════════════


class TestAlertToDict:
    def test_basic_conversion(self):
        svc = _make_service()
        alert = _make_alert_model()
        d = svc._alert_to_dict(alert)
        assert d["id"] == "alr_001"
        assert d["symbol"] == "فولاد"
        assert d["alert_type"] == "price_above"
        assert isinstance(d["condition"], dict)
        assert isinstance(d["channels"], list)

    def test_empty_condition(self):
        svc = _make_service()
        alert = _make_alert_model(condition=None)
        d = svc._alert_to_dict(alert)
        assert d["condition"] == {}

    def test_empty_channels(self):
        svc = _make_service()
        alert = _make_alert_model(channels=None)
        d = svc._alert_to_dict(alert)
        assert d["channels"] == []

    def test_triggered_count(self):
        svc = _make_service()
        alert = _make_alert_model(triggered_count=5, last_triggered=datetime(2024, 1, 15))
        d = svc._alert_to_dict(alert)
        assert d["triggered_count"] == 5
        assert d["last_triggered"] == datetime(2024, 1, 15)


# ════════════════════════════════════════════════════════════════
# 9. Edge cases
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEdgeCases:
    async def test_evaluate_exception_in_condition_parsing(self):
        svc = _make_service()
        alert = _make_alert_model(condition="invalid json")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [alert]
        svc.session.execute = AsyncMock(return_value=mock_result)

        triggered = await svc.evaluate_and_trigger("inst_001", "فولاد", "price_last", 5000)
        assert len(triggered) == 0

    async def test_create_alert_empty_channels(self):
        svc = _make_service()
        svc.session.add = MagicMock()
        svc.session.flush = AsyncMock()

        result = await svc.create_alert(
            user_id="user_001",
            instrument_id="inst_001",
            symbol="فولاد",
            alert_type="price_above",
            condition={},
            channels=[],
            description="",
        )
        assert result.success

    async def test_update_alert_partial_kwargs(self):
        svc = _make_service()
        alert = _make_alert_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = alert
        svc.session.execute = AsyncMock(return_value=mock_result)
        svc.session.flush = AsyncMock()

        result = await svc.update_alert("alr_001", "user_001", enabled=False)
        assert result.success
        assert alert.enabled is False
        assert alert.description == "قیمت بالای ۵۰۰۰"
