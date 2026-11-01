"""Deprecated alias for :mod:`core.resilience.circuit_breaker`.

This module used to contain a second, incompatible ``CircuitBreaker``
implementation. It now re-exports the canonical one; ``CircuitBreakerState``
remains as an alias of ``CircuitState`` so old imports keep resolving.
"""

from __future__ import annotations

from core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)

CircuitBreakerState = CircuitState

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitBreakerState",
    "CircuitState",
]
