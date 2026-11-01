"""Resilience primitives public surface.

``CircuitBreaker`` has a single implementation in
:mod:`core.resilience.circuit_breaker`.
"""

from __future__ import annotations

from core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    circuit_breaker,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "circuit_breaker",
]
