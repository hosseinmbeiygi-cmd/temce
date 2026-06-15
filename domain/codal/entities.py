from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class CodalEntity(BaseEntity):
    company_name: str = ""
    company_code: str = ""
    symbol: str = ""
    isin: str = ""
    registration_number: str = ""
    fiscal_year_end: str = ""
    industry: str = ""
    is_listed: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        company_name: str = "",
        company_code: str = "",
        symbol: str = "",
        isin: str = "",
        registration_number: str = "",
        fiscal_year_end: str = "",
        industry: str = "",
        is_listed: bool = True,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.company_name = company_name
        self.company_code = company_code
        self.symbol = symbol
        self.isin = isin
        self.registration_number = registration_number
        self.fiscal_year_end = fiscal_year_end
        self.industry = industry
        self.is_listed = is_listed
        self.extra = extra or {}
