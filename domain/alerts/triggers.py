from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.time import utc_now_naive
from domain.common.base_entity import BaseEntity


@dataclass
class AlertTrigger(BaseEntity):
    rule_id: str
    name: str
    instrument_id: str
    trigger_type: str = ""
    condition: str = ""
    threshold: float = 0.0
    operator: str = "gte"
    cooldown_seconds: int = 0
    last_fired_at: datetime | None = None
    fire_count: int = 0
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        rule_id: str,
        name: str,
        instrument_id: str,
        trigger_type: str = "",
        condition: str = "",
        threshold: float = 0.0,
        operator: str = "gte",
        cooldown_seconds: int = 0,
        last_fired_at: datetime | None = None,
        fire_count: int = 0,
        is_active: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.rule_id = rule_id
        self.name = name
        self.instrument_id = instrument_id
        self.trigger_type = trigger_type
        self.condition = condition
        self.threshold = threshold
        self.operator = operator
        self.cooldown_seconds = cooldown_seconds
        self.last_fired_at = last_fired_at
        self.fire_count = fire_count
        self.is_active = is_active
        self.extra = extra or {}

    def evaluate(self, current_value: float) -> bool:
        if not self.is_active:
            return False
        ops: dict[str, Callable[[float, float], bool]] = {
            "gte": lambda v, t: v >= t,
            "gt": lambda v, t: v > t,
            "lte": lambda v, t: v <= t,
            "lt": lambda v, t: v < t,
            "eq": lambda v, t: v == t,
            "neq": lambda v, t: v != t,
        }
        op_fn = ops.get(self.operator)
        if op_fn is None:
            return False
        return op_fn(current_value, self.threshold)

    def fire(self) -> None:
        self.fire_count += 1
        self.last_fired_at = utc_now_naive()
        self.mark_updated()
