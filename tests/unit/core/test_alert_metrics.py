"""Regression tests for audit finding F10 — alert-pipeline metrics and correlation id
(ممیزی 2026-11-28).

Four counter families are rendered through the shared in-process PrometheusExporter
(``core.metrics`` helpers → ``integrations.observability.prometheus_exporter``), so
they appear in the same ``/metrics`` output as the HTTP middleware metrics. Helpers
are best-effort: any exporter failure must never break the alert path.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.metrics import (
    ALERT_DELIVERY_OUTCOMES,
    ALERT_JOB_EVALUATIONS,
    ALERT_TRIGGERS,
    inc_alert_delivery,
    inc_alert_duplicate,
    inc_alert_job_evaluation,
    inc_alert_trigger,
)
from integrations.observability.prometheus_exporter import get_shared_exporter
from services.alert_service import AlertService


@pytest.fixture(autouse=True)
def _clean_exporter():
    exporter = get_shared_exporter()
    exporter.reset()
    yield
    exporter.reset()


def _counter_value(name: str, labels: dict[str, str]) -> float:
    return get_shared_exporter().counter(name, labels)


def test_job_evaluation_counter():
    inc_alert_job_evaluation("EvaluateAlertsJob", "success")
    inc_alert_job_evaluation("EvaluateAlertsJob", "skipped_market_closed", 2)
    assert _counter_value(ALERT_JOB_EVALUATIONS, {"job": "EvaluateAlertsJob", "outcome": "success"}) == 1.0
    assert _counter_value(ALERT_JOB_EVALUATIONS, {"job": "EvaluateAlertsJob", "outcome": "skipped_market_closed"}) == 2.0


def test_trigger_counter():
    inc_alert_trigger("price")
    assert _counter_value(ALERT_TRIGGERS, {"field": "price"}) == 1.0


def test_delivery_counter_with_amounts():
    inc_alert_delivery("engine", "telegram", "accepted", 3.0)
    assert _counter_value(ALERT_DELIVERY_OUTCOMES,
                          {"path": "engine", "channel": "telegram", "outcome": "accepted"}) == 3.0


def test_duplicate_counter():
    inc_alert_duplicate("conditional_opportunity")
    exporter = get_shared_exporter()
    text = exporter.export_prometheus()
    assert "alert_notification_duplicates_total" in text
    assert '"event_type":"conditional_opportunity"' in text or "'event_type'" in text or \
        "event_type" in text


def test_helpers_never_raise_when_exporter_unavailable():
    with patch("integrations.observability.prometheus_exporter.get_shared_exporter",
               side_effect=RuntimeError("no exporter")):
        # None of these may raise — metrics are best-effort by contract.
        inc_alert_job_evaluation("j", "success")
        inc_alert_trigger("price")
        inc_alert_delivery("threshold", "console", "not_configured")
        inc_alert_duplicate("state_changed")


@pytest.mark.asyncio
async def test_threshold_console_delivery_is_counted():
    """The console channel path (no DB, no network) flows into the delivery counter."""
    svc = AlertService(MagicMock())
    statuses = await svc._deliver_by_channel("test message", ["console"])
    assert statuses == {"console": "not_configured"}
    assert _counter_value(ALERT_DELIVERY_OUTCOMES,
                          {"path": "threshold", "channel": "console", "outcome": "not_configured"}) == 1.0


@pytest.mark.asyncio
async def test_evaluate_and_trigger_increments_trigger_metric():
    alert = MagicMock()
    alert.id = "alr_metric"
    alert.user_id = "usr_demo"
    alert.symbol = "فولاد"
    alert.instrument_id = ""
    alert.enabled = True
    alert.condition = json.dumps({"field": "price", "operator": "gte", "threshold": 5000.0,
                                  "cooldown_minutes": 30})
    alert.channels = json.dumps(["telegram"])
    alert.triggered_count = 0
    alert.last_triggered = None
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [alert]
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    svc = AlertService(session)
    with patch.object(svc, "_deliver_by_channel",
                      AsyncMock(return_value={"telegram": "delivered"})):
        triggered = await svc.evaluate_and_trigger("", alert.symbol, "price", 5200.0)
    assert len(triggered) == 1
    assert _counter_value(ALERT_TRIGGERS, {"field": "price"}) == 1.0
