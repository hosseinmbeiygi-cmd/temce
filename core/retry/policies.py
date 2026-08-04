"""Retry policy presets — canonical implementation lives in ``core.retry``.

The single source of truth for ``RetryPolicy`` is ``core.retry.RetryPolicy``
(used by providers, tests and the ``@retry`` decorator).  This module exists
for backward compatibility with imports like::

    from core.retry.policies import DefaultRetryPolicy

It also keeps the standalone backoff strategy classes (used by code that
wants a pluggable delay schedule) available.
"""

from __future__ import annotations

from core.retry import RetryPolicy  # noqa: F401  — canonical class


class DefaultRetryPolicy(RetryPolicy):
    """Moderate backoff: 3 retries, 1s base, up to 30s."""

    def __init__(self) -> None:
        super().__init__(max_retries=3, base_delay=1.0, max_delay=30.0)


class FastRetryPolicy(RetryPolicy):
    """Aggressive/quick retries: 2 retries, 0.1s base, up to 2s."""

    def __init__(self) -> None:
        super().__init__(max_retries=2, base_delay=0.1, max_delay=2.0)


class AggressiveRetryPolicy(RetryPolicy):
    """Long-horizon retries: 5 retries, 0.5s base, up to 60s."""

    def __init__(self) -> None:
        super().__init__(max_retries=5, base_delay=0.5, max_delay=60.0)


class NoRetryPolicy(RetryPolicy):
    def __init__(self) -> None:
        super().__init__(max_retries=0)


__all__ = [
    "RetryPolicy",
    "DefaultRetryPolicy",
    "FastRetryPolicy",
    "AggressiveRetryPolicy",
    "NoRetryPolicy",
]
