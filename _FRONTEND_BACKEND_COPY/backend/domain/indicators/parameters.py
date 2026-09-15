from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndicatorParameter:
    name: str = ""
    display_name: str = ""
    param_type: str = "int"
    default_value: Any = 0
    min_value: float | None = None
    max_value: float | None = None
    step: float = 1.0
    options: list[Any] = field(default_factory=list)
    description: str = ""
