from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class VolatilitySurface(BaseEntity):
    underlying_id: str
    date: date | None = None
    surface_data: dict[str, dict[str, float]] = field(default_factory=dict)
    model: str = "svi"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        underlying_id: str,
        date: date | None = None,
        surface_data: dict[str, dict[str, float]] | None = None,
        model: str = "svi",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.underlying_id = underlying_id
        self.date = date
        self.surface_data = surface_data or {}
        self.model = model
        self.extra = extra or {}

    def get_volatility(self, strike: float, expiry: str) -> float:
        expiry_str = str(expiry)
        if expiry_str in self.surface_data and str(strike) in self.surface_data[expiry_str]:
            return self.surface_data[expiry_str][str(strike)]
        return 0.0

    def add_point(self, expiry: str, strike: float, volatility: float) -> None:
        if expiry not in self.surface_data:
            self.surface_data[expiry] = {}
        self.surface_data[expiry][str(strike)] = volatility
        self.mark_updated()
