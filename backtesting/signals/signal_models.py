from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from domain.common.enum_types import SignalType


@dataclass
class Signal:
    instrument_id: str
    signal_type: SignalType
    strength: float = 1.0
    source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5


class SignalModel:
    def __init__(self, name: str = "") -> None:
        self.name = name or self.__class__.__name__

    def generate(self, data: dict[str, Any]) -> Signal | None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"SignalModel(name={self.name})"
