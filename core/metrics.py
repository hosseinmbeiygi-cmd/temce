"""Alert-pipeline metrics (audit F10, 2026-11-28).

Four counter families, rendered through the shared in-process PrometheusExporter
(``integrations.observability.prometheus_exporter.get_shared_exporter``) so they
appear in the same scrapeable ``/metrics`` output as the HTTP middleware metrics:

* ``alert_job_evaluations_total{job, outcome}``  — evaluation passes per job
  (success / skipped / failure) for EvaluateAlertsJob and MonitorAlertInstrumentsJob;
* ``alert_triggers_total{field}``                — threshold alerts whose condition
  held and were processed;
* ``alert_delivery_outcomes_total{path, channel, outcome}`` — per-channel delivery
  results on both alert paths (path ∈ threshold|engine; outcome ∈ accepted|failed|
  not_configured|skipped|suppressed);
* ``alert_notification_duplicates_total{event_type}`` — engine notifications dropped
  by the (user_id, dedupe_key) unique constraint.

Every helper is best-effort: a failure to reach the exporter must never break the
alert path — it is logged at debug level and dropped.
"""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)

ALERT_JOB_EVALUATIONS = "alert_job_evaluations_total"
ALERT_TRIGGERS = "alert_triggers_total"
ALERT_DELIVERY_OUTCOMES = "alert_delivery_outcomes_total"
ALERT_DUPLICATES = "alert_notification_duplicates_total"


def _exporter():
    try:
        from integrations.observability.prometheus_exporter import get_shared_exporter

        return get_shared_exporter()
    except Exception:  # noqa: BLE001 — metrics must never break the alert path
        return None


def _inc(name: str, labels: dict[str, str], value: float = 1.0) -> None:
    exporter = _exporter()
    if exporter is None:
        return
    try:
        exporter.inc(name, labels, value)
    except Exception:  # noqa: BLE001
        logger.debug("alert metric %s inc failed", name, exc_info=True)


def inc_alert_job_evaluation(job: str, outcome: str, value: float = 1.0) -> None:
    _inc(ALERT_JOB_EVALUATIONS, {"job": job, "outcome": outcome}, value)


def inc_alert_trigger(field: str) -> None:
    _inc(ALERT_TRIGGERS, {"field": field})


def inc_alert_delivery(path: str, channel: str, outcome: str, value: float = 1.0) -> None:
    _inc(ALERT_DELIVERY_OUTCOMES, {"path": path, "channel": channel, "outcome": outcome}, value)


def inc_alert_duplicate(event_type: str) -> None:
    _inc(ALERT_DUPLICATES, {"event_type": event_type})
