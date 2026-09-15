from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RateLimitRule:
    key: str
    limit: int
    window_seconds: int = 60
    burst: int = 1
    description: str = ""


@dataclass
class RateLimitState:
    key: str
    remaining: int
    reset_time: float
    limit: int
    window_seconds: int


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_after: float
    retry_after: float = 0.0


@dataclass
class RateLimitExceeded(Exception):
    key: str = ""
    limit: int = 0
    reset_after: float = 0.0
    retry_after: float = 0.0
