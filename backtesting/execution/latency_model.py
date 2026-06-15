from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class LatencyModel:
    mean_ms: float = 50.0
    std_ms: float = 20.0
    network_delay_ms: float = 10.0

    def compute_delay(self) -> float:
        import random

        processing = random.gauss(self.mean_ms, self.std_ms)
        return max(0.0, processing + self.network_delay_ms)

    def apply_latency(self, timestamp: datetime) -> datetime:
        delay_ms = self.compute_delay()
        return timestamp + timedelta(milliseconds=delay_ms)
