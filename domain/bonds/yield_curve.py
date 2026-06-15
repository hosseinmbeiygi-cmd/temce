from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class YieldCurvePoint:
    tenor: str = ""
    days: int = 0
    yield_rate: float = 0.0


@dataclass
class YieldCurve(BaseEntity):
    date: date | None = None
    points: list[YieldCurvePoint] = field(default_factory=list)
    curve_type: str = "spot"
    currency: str = "IRR"
    source: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        date: date | None = None,
        points: list[YieldCurvePoint] | None = None,
        curve_type: str = "spot",
        currency: str = "IRR",
        source: str = "",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.date = date
        self.points = points or []
        self.curve_type = curve_type
        self.currency = currency
        self.source = source
        self.extra = extra or {}

    def add_point(self, tenor: str, days: int, yield_rate: float) -> None:
        self.points.append(YieldCurvePoint(tenor=tenor, days=days, yield_rate=yield_rate))
        self.mark_updated()
