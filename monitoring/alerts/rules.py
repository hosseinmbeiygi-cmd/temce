from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger
from monitoring.alerts.manager import Alert, AlertSeverity, alert_manager

logger = get_logger(__name__)

ConditionFn = Callable[[dict[str, Any]], bool]


@dataclass
class AlertRule:
    name: str
    condition_fn: ConditionFn
    severity: AlertSeverity = AlertSeverity.WARNING
    message_template: str = ""
    cooldown_seconds: int = 300
    enabled: bool = True
    _last_triggered: datetime | None = field(default=None, repr=False)


class AlertRuleEngine:
    def __init__(self) -> None:
        self._rules: list[AlertRule] = []

    def add_rule(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, name: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    async def evaluate(self, metrics: dict[str, Any]) -> list[str]:
        triggered: list[str] = []
        now = datetime.now(UTC)
        for rule in self._rules:
            if not rule.enabled:
                continue
            if rule._last_triggered:
                elapsed = (now - rule._last_triggered).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue
            try:
                if rule.condition_fn(metrics):
                    message = rule.message_template.format(**metrics)
                    await alert_manager.send(
                        Alert(
                            title=f"Rule triggered: {rule.name}",
                            message=message,
                            severity=rule.severity,
                            source="alert_rule_engine",
                        )
                    )
                    rule._last_triggered = now
                    triggered.append(rule.name)
                    logger.warning("Alert rule '%s' triggered: %s", rule.name, message)
            except Exception as e:
                logger.error("Failed to evaluate rule '%s': %s", rule.name, e)
        return triggered


def _high_error_rate(metrics: dict[str, Any]) -> bool:
    total = metrics.get("api_requests_total", 0)
    errors = metrics.get("api_errors_total", 0)
    if total == 0:
        return False
    return (errors / total) > 0.05


def _data_stale(metrics: dict[str, Any]) -> bool:
    max_age = metrics.get("max_data_age_seconds", 0)
    return max_age > 3600


def _job_failure(metrics: dict[str, Any]) -> bool:
    failures = metrics.get("job_failures_total", 0)
    return failures > 0


def _provider_down(metrics: dict[str, Any]) -> bool:
    failed_providers = metrics.get("failed_providers", [])
    return len(failed_providers) > 0


high_error_rate = AlertRule(
    name="high_error_rate",
    condition_fn=_high_error_rate,
    severity=AlertSeverity.CRITICAL,
    message_template="API error rate is above threshold: {api_errors_total}/{api_requests_total}",
)

data_stale = AlertRule(
    name="data_stale",
    condition_fn=_data_stale,
    severity=AlertSeverity.WARNING,
    message_template="Data staleness exceeds threshold: {max_data_age_seconds}s",
)

job_failure = AlertRule(
    name="job_failure",
    condition_fn=_job_failure,
    severity=AlertSeverity.CRITICAL,
    message_template="Job failures detected: {job_failures_total}",
)

provider_down = AlertRule(
    name="provider_down",
    condition_fn=_provider_down,
    severity=AlertSeverity.CRITICAL,
    message_template="Provider(s) down: {failed_providers}",
)

alert_rule_engine = AlertRuleEngine()
alert_rule_engine.add_rule(high_error_rate)
alert_rule_engine.add_rule(data_stale)
alert_rule_engine.add_rule(job_failure)
alert_rule_engine.add_rule(provider_down)
