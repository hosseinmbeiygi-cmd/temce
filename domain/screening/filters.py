from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class FilterOperator:
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


@dataclass
class FilterCriterion:
    field: str = ""
    operator: str = "eq"
    value: Any = None
    value_to: Any = None


@dataclass
class ScreeningFilter:
    name: str = ""
    criteria: list[FilterCriterion] = field(default_factory=list)
    logic: str = "and"
    is_active: bool = True
