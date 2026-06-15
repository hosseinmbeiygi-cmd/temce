from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    strategy: str = "value"
    risk_tolerance: str = "moderate"
    horizon: str = "medium_term"


class RecommendationResponse(BaseModel):
    id: str
    symbol: str = ""
    action: str = ""
    confidence: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0
    rationale: str = ""
    strategy: str = ""
    risk_level: str = ""
    horizon: str = ""
    generated_at: str = ""
    expires_at: str = ""


class RecommendationListResponse(BaseModel):
    items: list[RecommendationResponse] = Field(default_factory=list)
    total: int = 0
