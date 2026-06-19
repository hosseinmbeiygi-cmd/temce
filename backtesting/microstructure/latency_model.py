from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class LatencyComponents:
    market_data: float = 5e-6
    decision: float = 10e-6
    order_routing: float = 20e-6
    exchange_processing: float = 5e-6
    network: float = 10e-6

    @property
    def total_seconds(self) -> float:
        return self.market_data + self.decision + self.order_routing + self.exchange_processing + self.network

    @property
    def total_milliseconds(self) -> float:
        return self.total_seconds * 1000


@dataclass
class LatencyModel:
    components: LatencyComponents = field(default_factory=LatencyComponents)
    jitter_std_pct: float = 0.2

    def total_latency_seconds(self) -> float:
        jitter = 1.0 + random.gauss(0, self.jitter_std_pct)
        return max(0, self.components.total_seconds * jitter)

    def total_latency_ms(self) -> float:
        return self.total_latency_seconds() * 1000

    def apply_to_timestamp(self, timestamp: datetime) -> datetime:
        delay = timedelta(seconds=self.total_latency_seconds())
        return timestamp + delay

    def get_effective_timestamp(self, event_timestamp: datetime) -> datetime:
        return self.apply_to_timestamp(event_timestamp)

    def market_data_lag(self) -> timedelta:
        jitter = 1.0 + random.gauss(0, self.jitter_std_pct)
        return timedelta(seconds=max(0, self.components.market_data * jitter))

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_data_ms": self.components.market_data * 1000,
            "decision_ms": self.components.decision * 1000,
            "order_routing_ms": self.components.order_routing * 1000,
            "exchange_processing_ms": self.components.exchange_processing * 1000,
            "network_ms": self.components.network * 1000,
            "total_ms": self.components.total_milliseconds,
            "jitter_std_pct": self.jitter_std_pct,
        }
