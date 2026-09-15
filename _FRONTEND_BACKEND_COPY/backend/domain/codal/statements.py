from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class FinancialStatement(BaseEntity):
    instrument_id: str
    statement_type: str = ""
    fiscal_year: str = ""
    period: str = ""
    publish_date: date | None = None
    items: dict[str, float] = field(default_factory=dict)
    currency: str = "IRR"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        statement_type: str = "",
        fiscal_year: str = "",
        period: str = "",
        publish_date: date | None = None,
        items: dict[str, float] | None = None,
        currency: str = "IRR",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.statement_type = statement_type
        self.fiscal_year = fiscal_year
        self.period = period
        self.publish_date = publish_date
        self.items = items or {}
        self.currency = currency
        self.extra = extra or {}

    def get_item(self, name: str) -> float:
        return self.items.get(name, 0.0)

    def set_item(self, name: str, value: float) -> None:
        self.items[name] = value
        self.mark_updated()
