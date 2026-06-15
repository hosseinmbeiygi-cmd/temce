from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from domain.common.base_entity import BaseEntity


@dataclass
class PredictionResult(BaseEntity):
    model_version_id: str
    instrument_id: str
    symbol: str = ""
    prediction: float = 0.0
    probability: float = 0.0
    expected_return: float = 0.0
    confidence_interval_low: float = 0.0
    confidence_interval_high: float = 0.0
    prediction_date: str = ""
    features_used: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        model_version_id: str,
        instrument_id: str,
        symbol: str = "",
        prediction: float = 0.0,
        probability: float = 0.0,
        expected_return: float = 0.0,
        confidence_interval_low: float = 0.0,
        confidence_interval_high: float = 0.0,
        prediction_date: str = "",
        features_used: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__(id, created_at, updated_at)
        self.model_version_id = model_version_id
        self.instrument_id = instrument_id
        self.symbol = symbol
        self.prediction = prediction
        self.probability = probability
        self.expected_return = expected_return
        self.confidence_interval_low = confidence_interval_low
        self.confidence_interval_high = confidence_interval_high
        self.prediction_date = prediction_date
        self.features_used = features_used or []
        self.extra = extra or {}
