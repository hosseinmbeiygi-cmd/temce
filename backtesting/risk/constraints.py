from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from backtesting.types import OrderEvent


@dataclass
class RiskConstraint:
    name: str
    check: Callable[[OrderEvent, dict[str, Any]], bool]
    message: str = ""


class RiskConstraints:
    def __init__(self) -> None:
        self._constraints: list[RiskConstraint] = []

    def add(self, constraint: RiskConstraint) -> None:
        self._constraints.append(constraint)

    def check_all(self, order: OrderEvent, context: dict[str, Any]) -> list[str]:
        violations: list[str] = []
        for c in self._constraints:
            if not c.check(order, context):
                violations.append(c.message or c.name)
        return violations

    def is_allowed(self, order: OrderEvent, context: dict[str, Any]) -> bool:
        return len(self.check_all(order, context)) == 0

    def clear(self) -> None:
        self._constraints.clear()
