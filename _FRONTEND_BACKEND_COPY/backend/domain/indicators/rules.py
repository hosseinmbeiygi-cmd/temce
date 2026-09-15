from __future__ import annotations

from typing import Any

from domain.indicators.parameters import IndicatorParameter


def validate_indicator_parameter(param: IndicatorParameter, value: Any) -> bool:
    if param.param_type == "int" and not isinstance(value, int):
        return False
    if param.param_type == "float" and not isinstance(value, (int, float)):
        return False
    if param.min_value is not None and value < param.min_value:
        return False
    return not (param.max_value is not None and value > param.max_value)


def validate_indicator_value(value: float) -> bool:
    return True


def is_overlay_indicator(category: str) -> bool:
    return category == "overlay"
