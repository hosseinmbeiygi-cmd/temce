from __future__ import annotations

from pydantic import BaseModel, Field


class LayerScores(BaseModel):
    accumulation: float = Field(default=0.0, description="امتیاز انباشت")
    absorption: float = Field(default=0.0, description="امتیاز جذب عرضه")
    float_lock: float = Field(default=0.0, description="امتیاز قفل شناوری")
    breakout_readiness: float = Field(default=0.0, description="امتیاز آمادگی شکست")


class Penalties(BaseModel):
    distribution_risk: float = 0.0
    fake_breakout_risk: float = 0.0
    dead_compression: float = 0.0


class SmartMoneyAnalysisResponse(BaseModel):
    symbol: str = ""
    smart_money_score: float = 0.0
    phase: str = ""
    scores: LayerScores = Field(default_factory=LayerScores)
    penalties: Penalties = Field(default_factory=Penalties)
    features: dict[str, float] = Field(default_factory=dict)
    breakout_features: dict[str, float] = Field(default_factory=dict)
