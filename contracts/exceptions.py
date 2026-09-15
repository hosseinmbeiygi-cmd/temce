# contracts/exceptions.py — Precompute / API domain exceptions.
# Follows the same hierarchy pattern as core/exceptions.py.
from __future__ import annotations


class PrecomputeError(Exception):
    """Base for all precompute-domain errors."""
    pass


class PrecomputeNotRunningError(PrecomputeError):
    """Client tried to query status / result when no job is active."""
    pass


class SymbolNotFoundError(PrecomputeError):
    """Requested symbol has no precomputed result (never computed or expired)."""
    pass


class StaleResultError(PrecomputeError):
    """Result exists but is past its freshness window."""
    pass


class PrecomputeJobCollisionError(PrecomputeError):
    """A precompute job is already running; start was called again."""
    pass
