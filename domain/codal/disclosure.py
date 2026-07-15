from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class Disclosure(BaseEntity):
    instrument_id: str
    title: str
    symbol: str = ""
    company_name: str = ""
    publish_date: date | None = None
    fiscal_year: str = ""
    period: str = ""
    disclosure_type: str = ""
    category: str = ""
    summary: str = ""
    url: str = ""
    data_source: str = "codal"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        title: str,
        symbol: str = "",
        company_name: str = "",
        publish_date: date | None = None,
        fiscal_year: str = "",
        period: str = "",
        disclosure_type: str = "",
        category: str = "",
        summary: str = "",
        url: str = "",
        data_source: str = "codal",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.title = title
        self.symbol = symbol
        self.company_name = company_name
        self.publish_date = publish_date
        self.fiscal_year = fiscal_year
        self.period = period
        self.disclosure_type = disclosure_type
        self.category = category
        self.summary = summary
        self.url = url
        self.data_source = data_source
        self.extra = extra or {}
