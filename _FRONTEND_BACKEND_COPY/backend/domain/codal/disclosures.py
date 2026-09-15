from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from domain.common.base_entity import BaseEntity


class DisclosureCategory:
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    MONTHLY = "monthly"
    EXTRAORDINARY = "extraordinary"
    BOARD_REPORT = "board_report"
    AUDITOR_REPORT = "auditor_report"
    CAPITAL_INCREASE = "capital_increase"
    GENERAL_ASSEMBLY = "general_assembly"
    OTHER = "other"


@dataclass
class CodalDisclosure(BaseEntity):
    instrument_id: str
    title: str = ""
    symbol: str = ""
    publish_date: date | None = None
    fiscal_year: str = ""
    period: str = ""
    disclosure_type: str = ""
    category: str = ""
    summary: str = ""
    url: str = ""
    is_important: bool = False
    data_source: str = "codal"
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        instrument_id: str,
        title: str = "",
        symbol: str = "",
        publish_date: date | None = None,
        fiscal_year: str = "",
        period: str = "",
        disclosure_type: str = "",
        category: str = "",
        summary: str = "",
        url: str = "",
        is_important: bool = False,
        data_source: str = "codal",
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.instrument_id = instrument_id
        self.title = title
        self.symbol = symbol
        self.publish_date = publish_date
        self.fiscal_year = fiscal_year
        self.period = period
        self.disclosure_type = disclosure_type
        self.category = category
        self.summary = summary
        self.url = url
        self.is_important = is_important
        self.data_source = data_source
        self.extra = extra or {}
