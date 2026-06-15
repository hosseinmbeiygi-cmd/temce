from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class IndicatorDefinition(BaseEntity):
    name: str
    display_name: str = ""
    category: str = ""
    formula: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    min_inputs: int = 1
    max_inputs: int = 1
    output_type: str = "float"
    is_builtin: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        name: str,
        display_name: str = "",
        category: str = "",
        formula: str = "",
        description: str = "",
        parameters: dict[str, Any] | None = None,
        min_inputs: int = 1,
        max_inputs: int = 1,
        output_type: str = "float",
        is_builtin: bool = False,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.display_name = display_name
        self.category = category
        self.formula = formula
        self.description = description
        self.parameters = parameters or {}
        self.min_inputs = min_inputs
        self.max_inputs = max_inputs
        self.output_type = output_type
        self.is_builtin = is_builtin
        self.extra = extra or {}


@dataclass
class IndicatorValue(BaseEntity):
    indicator_id: str
    instrument_id: str
    value: float = 0.0
    symbol: str = ""
    timeframe: str = "1d"
    date: str = ""
    time: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        indicator_id: str,
        instrument_id: str,
        value: float = 0.0,
        symbol: str = "",
        timeframe: str = "1d",
        date: str = "",
        time: str = "",
        parameters: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.indicator_id = indicator_id
        self.instrument_id = instrument_id
        self.value = value
        self.symbol = symbol
        self.timeframe = timeframe
        self.date = date
        self.time = time
        self.parameters = parameters or {}
        self.extra = extra or {}
