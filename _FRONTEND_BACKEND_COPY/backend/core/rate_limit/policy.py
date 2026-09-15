from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RateLimitPolicy:
    name: str
    requests_per_second: float = 10.0
    burst_size: int = 20
    concurrent_limit: int = 5
    queue_timeout: float = 30.0
    retry_after_seconds: int = 60
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "requests_per_second": self.requests_per_second,
            "burst_size": self.burst_size,
            "concurrent_limit": self.concurrent_limit,
            "queue_timeout": self.queue_timeout,
            "retry_after_seconds": self.retry_after_seconds,
            "enabled": self.enabled,
        }


DEFAULT_POLICIES: dict[str, RateLimitPolicy] = {
    "api_global": RateLimitPolicy("api_global", requests_per_second=60, burst_size=100),
    "provider_tsetmc": RateLimitPolicy("provider_tsetmc", requests_per_second=10, burst_size=20),
    "provider_codal": RateLimitPolicy("provider_codal", requests_per_second=5, burst_size=10),
    "provider_broker": RateLimitPolicy("provider_broker", requests_per_second=20, burst_size=40),
    "ml_inference": RateLimitPolicy("ml_inference", requests_per_second=100, burst_size=200),
}
