from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SymbolAlertCreate(BaseModel):
    symbol: str = ""
    market: str = ""
    trigger_rules: dict[str, Any] = Field(default_factory=dict)
    base_price: float = 0.0


class SymbolAlertResponse(BaseModel):
    id: str
    user_id: str = ""
    symbol: str = ""
    market: str = ""
    base_price: float = 0.0
    trigger_rules: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime | None = None


class SymbolDecisionHubResponse(BaseModel):
    symbol: str
    user_id: str = ""
    assessment: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime | None = None
    status: str = "partial"


class SymbolListEntry(BaseModel):
    id: str
    symbol: str
    market: str = ""
    base_price: float = 0.0
    is_active: bool = True
    last_evaluated_at: datetime | None = None
    assessment_status: str = "pending"
