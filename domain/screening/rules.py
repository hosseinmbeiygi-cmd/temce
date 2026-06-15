from __future__ import annotations

from typing import Any

from domain.screening.filters import FilterOperator

VALID_OPERATORS = {
    FilterOperator.EQ,
    FilterOperator.NEQ,
    FilterOperator.GT,
    FilterOperator.GTE,
    FilterOperator.LT,
    FilterOperator.LTE,
    FilterOperator.BETWEEN,
    FilterOperator.IN,
    FilterOperator.NOT_IN,
    FilterOperator.CONTAINS,
    FilterOperator.STARTS_WITH,
    FilterOperator.ENDS_WITH,
}


def validate_filter_operator(operator: str) -> bool:
    return operator in VALID_OPERATORS


def validate_filter_value(operator: str, value: Any) -> bool:
    if operator == FilterOperator.BETWEEN:
        return isinstance(value, (list, tuple)) and len(value) == 2
    if operator in (FilterOperator.IN, FilterOperator.NOT_IN):
        return isinstance(value, (list, tuple)) and len(value) > 0
    return value is not None


def combine_filter_results(results: list[bool], logic: str) -> bool:
    if logic == "or":
        return any(results)
    return all(results)
