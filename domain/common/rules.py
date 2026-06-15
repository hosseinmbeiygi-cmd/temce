from __future__ import annotations

from collections.abc import Callable
from typing import Any

from domain.common.domain_error import DomainRuleViolation


class BusinessRule:
    def __init__(self, rule_name: str, message: str = "") -> None:
        self._rule_name = rule_name
        self._message = message or f"Rule '{rule_name}' violated"

    @property
    def rule_name(self) -> str:
        return self._rule_name

    def is_satisfied(self) -> bool:
        return True

    def check(self) -> None:
        if not self.is_satisfied():
            raise DomainRuleViolation(rule=self._rule_name, message=self._message)


class PredicateRule(BusinessRule):
    def __init__(self, rule_name: str, predicate: Callable[[], bool], message: str = "") -> None:
        super().__init__(rule_name, message)
        self._predicate = predicate

    def is_satisfied(self) -> bool:
        return self._predicate()


def validate_required(value: Any, field_name: str) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise DomainRuleViolation(rule="required_field", message=f"{field_name} is required")


def validate_positive(value: float, field_name: str) -> None:
    if value <= 0:
        raise DomainRuleViolation(rule="positive_value", message=f"{field_name} must be positive")


def validate_non_negative(value: float, field_name: str) -> None:
    if value < 0:
        raise DomainRuleViolation(rule="non_negative", message=f"{field_name} must be >= 0")
