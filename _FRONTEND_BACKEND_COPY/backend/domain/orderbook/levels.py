from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrderBookLevelDetail:
    price: float = 0.0
    volume: int = 0
    order_count: int = 0
    side: str = ""
    total_value: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.total_value = self.price * self.volume
