from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from schemas.api.legal import LegalDisclaimerMixin


class PortfolioCreate(BaseModel):
    name: str
    description: str = ""
    initial_capital: float = 0.0
    currency: str = "IRR"


class PortfolioResponse(BaseModel, LegalDisclaimerMixin):
    id: str
    name: str = ""
    description: str = ""
    initial_capital: float = 0.0
    current_value: float = 0.0
    total_return_pct: float = 0.0
    positions: list[dict[str, Any]] = Field(default_factory=list)
    currency: str = "IRR"
    created_at: str = ""
    updated_at: str = ""


class PortfolioListResponse(BaseModel):
    items: list[PortfolioResponse] = Field(default_factory=list)
    total: int = 0
