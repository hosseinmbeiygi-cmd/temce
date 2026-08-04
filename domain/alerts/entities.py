from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Alert(BaseEntity):
    instrument_id: str
    rule_id: str
    symbol: str = ""
    alert_type: str = ""
    message: str = ""
    severity: str = "info"
    value: float = 0.0
    threshold: float = 0.0
    direction: str = ""
    is_read: bool = False
    is_triggered: bool = False
    triggered_at: datetime | None = None
    extra: dict[str, Any] = dc_field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        rule_id: str,
        symbol: str = "",
        alert_type: str = "",
        message: str = "",
        severity: str = "info",
        value: float = 0.0,
        threshold: float = 0.0,
        direction: str = "",
        is_read: bool = False,
        is_triggered: bool = False,
        triggered_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.rule_id = rule_id
        self.symbol = symbol
        self.alert_type = alert_type
        self.message = message
        self.severity = severity
        self.value = value
        self.threshold = threshold
        self.direction = direction
        self.is_read = is_read
        self.is_triggered = is_triggered
        self.triggered_at = triggered_at
        self.extra = extra or {}

    def mark_read(self) -> None:
        self.is_read = True
        self.mark_updated()

    def mark_triggered(self) -> None:
        self.is_triggered = True
        self.triggered_at = datetime.now()
        self.mark_updated()


@dataclass
class AlertRule(BaseEntity):
    name: str
    instrument_id: str
    symbol: str = ""
    alert_type: str = ""
    field: str = ""
    operator: str = "gte"
    threshold: float = 0.0
    severity: str = "info"
    is_active: bool = True
    cooldown_minutes: int = 0
    last_triggered_at: datetime | None = None
    extra: dict[str, Any] = dc_field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        instrument_id: str,
        symbol: str = "",
        alert_type: str = "",
        field: str = "",
        operator: str = "gte",
        threshold: float = 0.0,
        severity: str = "info",
        is_active: bool = True,
        cooldown_minutes: int = 0,
        last_triggered_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.alert_type = alert_type
        self.field = field
        self.operator = operator
        self.threshold = threshold
        self.severity = severity
        self.is_active = is_active
        self.cooldown_minutes = cooldown_minutes
        self.last_triggered_at = last_triggered_at
        self.extra = extra or {}

    def activate(self) -> None:
        self.is_active = True
        self.mark_updated()

    def deactivate(self) -> None:
        self.is_active = False
        self.mark_updated()
