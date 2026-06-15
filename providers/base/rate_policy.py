from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RatePolicy:
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    concurrent_limit: int = 5
    retry_on_limit: bool = True
    max_retry_wait: int = 60

    @property
    def delay_between_requests(self) -> float:
        return 60.0 / self.requests_per_minute
