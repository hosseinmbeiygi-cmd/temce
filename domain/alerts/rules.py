from __future__ import annotations

from datetime import timedelta

from core.time import utc_now_naive
from domain.alerts.entities import AlertRule


def is_rule_active(rule: AlertRule) -> bool:
    return rule.is_active


def is_in_cooldown(rule: AlertRule) -> bool:
    if rule.cooldown_minutes <= 0 or rule.last_triggered_at is None:
        return False
    return utc_now_naive() - rule.last_triggered_at < timedelta(minutes=rule.cooldown_minutes)


def can_fire_alert(rule: AlertRule) -> bool:
    return rule.is_active and not is_in_cooldown(rule)


def validate_operator(operator: str) -> bool:
    return operator in ("gte", "gt", "lte", "lt", "eq", "neq")


def validate_severity(severity: str) -> bool:
    return severity in ("info", "warning", "critical", "emergency")
